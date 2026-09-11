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
from pdf.bulk_processor import parse_data_file, _find_col_case_insensitive, sanitize_filename

load_dotenv_if_exists()


def process_bulk_jpeg_edits(
    jpeg_template_path: str,
    data_file_path: str,
    output_dir: str,
    mapping_config: List[Dict[str, Any]],
    send_email_toggle: bool = False,
    email_column_name: Optional[str] = None,
    email_subject: Optional[str] = "Your Document",
    email_body: Optional[str] = "Please find attached your customized document.",
    smtp_config: Optional[Dict[str, Any]] = None,
    progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None
) -> Dict[str, Any]:
    """Bulk processes JPEG image edits from Excel/CSV data file.

    Args:
        jpeg_template_path: Path to base JPEG template image.
        data_file_path: Path to CSV or Excel file containing candidate data.
        output_dir: Output directory path to save generated JPEG files.
        mapping_config: List of mappings.
        send_email_toggle: Toggle whether automated email dispatch is enabled.
        email_column_name: Optional Excel column containing recipient emails.
        email_subject: Email subject text.
        email_body: Email body text.
        smtp_config: Dict with SMTP / Brevo credentials.
        progress_callback: Callback function receiving progress dict updates.

    Returns:
        Summary dict containing counts, errors, output zip path, and email stats.
    """
    load_dotenv_if_exists()

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

    smtp_cfg = smtp_config or {}
    sender_email = (smtp_cfg.get("sender_email") or "").strip() or os.environ.get("SMTP_SENDER_EMAIL", "").strip()
    sender_password = (smtp_cfg.get("sender_password") or "").strip() or os.environ.get("SMTP_SENDER_PASSWORD", "").strip()
    host = (smtp_cfg.get("host") or "").strip() or os.environ.get("SMTP_HOST", "smtp.hostinger.com").strip()
    port_raw = smtp_cfg.get("port", 0)
    try:
        port = int(port_raw or os.environ.get("SMTP_PORT", 0) or 465)
    except Exception:
        port = 465

    batch_sender: Optional[SMTPBatchSender] = None
    email_errors: List[Dict[str, Any]] = []

    # Pre-flight check: if email is enabled, verify credentials and test connection BEFORE processing
    if send_email_toggle:
        if not sender_email or not sender_password:
            return {
                "success": False,
                "message": (
                    "Email dispatch is enabled but SMTP credentials are missing. "
                    "Please fill in Sender Email and Password in the Email Dispatch section, "
                    "or set SMTP_SENDER_EMAIL and SMTP_SENDER_PASSWORD in your .env file."
                )
            }
        if not email_column_name:
            return {
                "success": False,
                "message": "Email dispatch is enabled but no recipient email column was selected."
            }

        batch_sender = SMTPBatchSender(
            host=host,
            port=port,
            sender_email=sender_email,
            sender_password=sender_password
        )
        preflight = batch_sender.connect()
        if not preflight.get("success"):
            return {
                "success": False,
                "message": f"Pre-flight Email Verification Failed: {preflight.get('error')}. Please check your SMTP credentials."
            }

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

    processed_files: List[str] = []
    used_filenames: set = set()
    sent_emails_count = 0
    failed_emails_count = 0
    errors: List[str] = []

    try:
        for idx, row in enumerate(data_rows, start=1):
            replacements: List[Dict[str, Any]] = []
            insertions: List[Dict[str, Any]] = []

            for map_item in mapping_config:
                col_name = map_item.get("excel_column")
                cell_value = ""
                if col_name:
                    found_val = _find_col_case_insensitive(row, col_name)
                    if found_val is not None:
                        cell_value = str(found_val).strip()
                    else:
                        cell_value = str(col_name).strip()

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

            # Create file name based on candidate name or fallback column / index
            cand_name_val = None
            for col_key in ["Name", "NAME", "name", "Full_Name", "Full Name", "Candidate_Name", "Candidate Name"]:
                cand_name_val = _find_col_case_insensitive(row, col_key)
                if cand_name_val and str(cand_name_val).strip():
                    break

            if not cand_name_val or not str(cand_name_val).strip():
                for k, v in row.items():
                    if "name" in str(k).lower() and v and str(v).strip():
                        cand_name_val = str(v).strip()
                        break

            raw_cand_name = str(cand_name_val or f"candidate_{idx}").strip()

            # Remove extension if already present in raw candidate name
            clean_name = raw_cand_name
            for ext in [".jpeg", ".jpg", ".png", ".JPEG", ".JPG", ".PNG"]:
                if clean_name.endswith(ext):
                    clean_name = clean_name[:-len(ext)].strip()
                    break

            safe_basename = sanitize_filename(clean_name)
            if not safe_basename or safe_basename == "document":
                safe_basename = f"candidate_{idx}"

            out_filename = f"{safe_basename}.jpeg"
            if out_filename in used_filenames:
                out_filename = f"{safe_basename}_{idx}.jpeg"
            used_filenames.add(out_filename)

            out_filepath = os.path.join(output_dir, out_filename)

            edit_res = edit_jpeg(jpeg_template_path, out_filepath, replacements=replacements, insertions=insertions)
            if not edit_res.get("success"):
                errors.append(f"Row {idx}: {edit_res.get('error')}")
                continue

            processed_files.append(out_filepath)

            # Send Email if configured
            if send_email_toggle and batch_sender and email_column_name:
                recipient = _find_col_case_insensitive(row, email_column_name)
                if recipient and "@" in recipient:
                    mail_res = batch_sender.send_one(
                        to_email=recipient.strip(),
                        subject=email_subject or "Your Document",
                        body_text=email_body or "Please find attached your customized JPEG document.",
                        pdf_path=out_filepath
                    )
                    if mail_res.get("success"):
                        sent_emails_count += 1
                    else:
                        failed_emails_count += 1
                        err_msg = mail_res.get("error", "Unknown email error")
                        email_errors.append({"row": idx, "recipient": recipient, "error": err_msg})
                        errors.append(f"Row {idx} email failed ({recipient}): {err_msg}")
                else:
                    failed_emails_count += 1
                    err_msg = f"No valid email address found in column '{email_column_name}' for row {idx}."
                    email_errors.append({"row": idx, "recipient": recipient or "(empty)", "error": err_msg})
                    errors.append(f"Row {idx} email failed: {err_msg}")

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
        "success": len(processed_files) > 0,
        "total_rows": total_rows,
        "generated_count": len(processed_files),
        "sent_emails_count": sent_emails_count,
        "failed_emails_count": failed_emails_count,
        "email_errors": email_errors,
        "zip_file": zip_filename,
        "zip_path": zip_filepath,
        "zip_filepath": zip_filepath,
        "zip_download_url": f"/jpeg/download/{zip_filename}",
        "errors": errors
    }
