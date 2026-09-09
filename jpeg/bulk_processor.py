"""JPEG Bulk Processor Engine.

Processes multiple JPEG images using a base JPEG template image + Excel/CSV data rows.
Maps Excel columns to target text replacements and free-space insertions.
Packages generated JPEGs into a zip archive and dispatches customized emails to candidates.
"""

from typing import Dict, Any, List, Optional, Callable
import os
import shutil
import zipfile
import uuid
import json
from jpeg.editor import edit_jpeg
from pdf.email_sender import SMTPBatchSender, load_dotenv_if_exists
from pdf.bulk_processor import parse_data_file

load_dotenv_if_exists()


def process_bulk_jpeg_edits(
    jpeg_template_path: str,
    data_file_path: str,
    output_dir: str,
    mapping_config: List[Dict[str, Any]],
    email_column_name: Optional[str] = None,
    email_subject: Optional[str] = "Your Document",
    email_body: Optional[str] = "Please find attached your document.",
    smtp_config: Optional[Dict[str, Any]] = None,
    progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None
) -> Dict[str, Any]:
    """Bulk processes JPEG image edits from Excel/CSV data file.

    Args:
        jpeg_template_path: Path to base JPEG template image.
        data_file_path: Path to CSV or Excel file containing candidate data.
        output_dir: Output directory path to save generated JPEG files.
        mapping_config: List of mappings, e.g.:
          [
            {"field": "Name", "excel_column": "Full_Name", "is_free_space": False},
            {"x": 150, "y": 300, "excel_column": "Issue_Date", "is_free_space": True, "font_size": 18, "font_color": "#000000"}
          ]
        email_column_name: Optional Excel column containing recipient emails.
        email_subject: Email subject text.
        email_body: Email body text.
        smtp_config: Dict with SMTP / Brevo credentials.
        progress_callback: Callback function receiving progress dict updates.

    Returns:
        Summary dict containing counts, errors, output zip path, and email stats.
    """
    if not os.path.exists(jpeg_template_path):
        return {"success": False, "message": f"Base JPEG template image not found: {jpeg_template_path}"}

    if not os.path.exists(data_file_path):
        return {"success": False, "message": f"Data file (Excel/CSV) not found: {data_file_path}"}

    try:
        data_rows = parse_data_file(data_file_path)
    except Exception as e:
        return {"success": False, "message": f"Failed to parse Excel/CSV data file: {str(e)}"}

    if not data_rows:
        return {"success": False, "message": "Excel/CSV data file contains no data rows."}

    os.makedirs(output_dir, exist_ok=True)
    total_rows = len(data_rows)

    def notify_progress(row_idx: int, step_name: str, next_name: str, sent_emails: int = 0, failed_emails: int = 0):
        if progress_callback:
            pct = int((row_idx / total_rows) * 100) if total_rows > 0 else 0
            progress_callback({
                "current_row": row_idx,
                "total_rows": total_rows,
                "progress_percent": pct,
                "status_step": step_name,
                "next_step": next_name,
                "sent_emails_count": sent_emails,
                "failed_emails_count": failed_emails,
                "generated_count": row_idx
            })

    notify_progress(0, "Initializing bulk JPEG generation...", "Processing row 1 data...")

    # Setup Batch Email Sender if enabled
    batch_sender: Optional[SMTPBatchSender] = None
    if smtp_config and email_column_name:
        sender_email = (smtp_config.get("sender_email") or "").strip() or None
        sender_password = (smtp_config.get("sender_password") or "").strip() or None
        host = (smtp_config.get("host") or "").strip() or None
        port_raw = smtp_config.get("port", 0)
        try:
            port = int(port_raw) if port_raw else 587
        except Exception:
            port = 587

        if sender_email and sender_password:
            batch_sender = SMTPBatchSender(
                host=host or "smtp.hostinger.com",
                port=port,
                sender_email=sender_email,
                sender_password=sender_password
            )
            conn_res = batch_sender.connect()
            if not conn_res.get("success"):
                return {"success": False, "message": f"Email authentication failed: {conn_res.get('error')}"}

    processed_files: List[str] = []
    sent_emails_count = 0
    failed_emails_count = 0
    errors: List[str] = []

    try:
        for idx, row in enumerate(data_rows, start=1):
            replacements: List[Dict[str, Any]] = []
            insertions: List[Dict[str, Any]] = []

            for map_item in mapping_config:
                col_name = map_item.get("excel_column")
                cell_value = str(row.get(col_name, "")).strip() if col_name else ""

                is_free_space = map_item.get("is_free_space", False)
                if is_free_space:
                    insertions.append({
                        "x": map_item.get("x"),
                        "y": map_item.get("y"),
                        "anchor": map_item.get("anchor"),
                        "text": cell_value,
                        "font_size": map_item.get("font_size"),
                        "font_color": map_item.get("font_color")
                    })
                else:
                    target_field = map_item.get("field") or map_item.get("target")
                    if target_field:
                        replacements.append({
                            "target": target_field,
                            "new_value": cell_value,
                            "box": map_item.get("box")
                        })

            # Create file name based on candidate name or index
            cand_name = str(row.get("Name") or row.get("Full_Name") or row.get("Candidate_Name") or f"candidate_{idx}").strip()
            safe_name = "".join(c for c in cand_name if c.isalnum() or c in (" ", "_", "-")).replace(" ", "_")
            out_filename = f"edited_{safe_name}_{idx}.jpg"
            out_filepath = os.path.join(output_dir, out_filename)

            edit_res = edit_jpeg(jpeg_template_path, out_filepath, replacements=replacements, insertions=insertions)
            if not edit_res.get("success"):
                errors.append(f"Row {idx}: {edit_res.get('error')}")
                continue

            processed_files.append(out_filepath)

            # Send Email if configured
            if batch_sender and email_column_name:
                recipient = str(row.get(email_column_name, "")).strip()
                if recipient and "@" in recipient:
                    mail_res = batch_sender.send_one(
                        to_email=recipient,
                        subject=email_subject or "Your Document",
                        body_text=email_body or "Please find attached your edited JPEG document.",
                        pdf_path=out_filepath  # Attachment works for JPEG via updated email_sender
                    )
                    if mail_res.get("success"):
                        sent_emails_count += 1
                    else:
                        failed_emails_count += 1
                        errors.append(f"Row {idx} email failed ({recipient}): {mail_res.get('error')}")

            next_label = f"Processing row {idx+1}..." if idx < total_rows else "Finalizing zip archive..."
            notify_progress(idx, f"Generated JPEG {idx}/{total_rows}", next_label, sent_emails_count, failed_emails_count)

    finally:
        if batch_sender:
            batch_sender.close()

    # Package output files into zip archive
    zip_filename = f"bulk_jpeg_export_{uuid.uuid4().hex[:8]}.zip"
    zip_filepath = os.path.join(output_dir, zip_filename)

    with zipfile.ZipFile(zip_filepath, "w", zipfile.ZIP_DEFLATED) as zipf:
        for fpath in processed_files:
            zipf.write(fpath, arcname=os.path.basename(fpath))

    return {
        "success": True,
        "total_rows": total_rows,
        "generated_count": len(processed_files),
        "sent_emails_count": sent_emails_count,
        "failed_emails_count": failed_emails_count,
        "zip_file": zip_filename,
        "zip_download_url": f"/jpeg/download/{zip_filename}",
        "errors": errors
    }
