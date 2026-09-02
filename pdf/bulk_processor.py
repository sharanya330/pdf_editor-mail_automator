"""Bulk PDF Generation Engine.

Parses Excel (.xlsx) or CSV (.csv) data files and generates customized PDFs
for every row in bulk using explicit field-to-column mappings, packaged into a ZIP archive.
"""

import os
import re
import csv
import zipfile
from typing import Dict, Any, List, Optional, Callable
import openpyxl

from pdf.analyzer import analyze_pdf
from pdf.field_resolver import build_edit_plan
from pdf.text_editor import edit_native_text_pdf
from pdf.validator import validate_pdf_edit
from pdf.email_sender import send_email_with_pdf_attachment, test_smtp_connection, SMTPBatchSender, load_dotenv_if_exists


def sanitize_filename(name: str) -> str:
    """Sanitizes a string to be a safe filesystem filename."""
    clean = re.sub(r'[\\/*?:"<>|]', '_', name).strip()
    return clean if clean else "document"


def _find_col_case_insensitive(row_dict: Dict[str, str], col_name: str) -> Optional[str]:
    """Finds a column value by case-insensitive key match."""
    col_lower = col_name.strip().lower()
    for k, v in row_dict.items():
        if k.strip().lower() == col_lower:
            return v
    return None


def parse_data_file(file_path: str) -> List[Dict[str, str]]:
    """Parses a CSV or Excel file into a list of row dictionaries."""
    rows = []
    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".csv":
        with open(file_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for r in reader:
                clean_row = {k.strip(): str(v).strip() for k, v in r.items() if k and v is not None}
                if any(clean_row.values()):
                    rows.append(clean_row)
    elif ext in (".xlsx", ".xls"):
        wb = openpyxl.load_workbook(file_path, data_only=True)
        sheet = wb.active
        header = None
        for row in sheet.iter_rows(values_only=True):
            if not row or not any(c is not None and str(c).strip() != "" for c in row):
                continue
            non_empty_count = sum(1 for c in row if c is not None and str(c).strip() != "")
            # Header is the first row with at least 2 non-empty values (skips single-cell title blocks)
            if header is None:
                if non_empty_count >= 2 or len(row) == 1:
                    header = [str(c).strip() if c is not None else f"col_{idx}" for idx, c in enumerate(row)]
            else:
                row_dict = {}
                for idx, cell in enumerate(row):
                    if idx < len(header):
                        val = str(cell).strip() if cell is not None else ""
                        row_dict[header[idx]] = val
                if any(row_dict.values()):
                    rows.append(row_dict)
        wb.close()
    else:
        raise ValueError(f"Unsupported data file extension: {ext}. Only .csv and .xlsx are supported.")

    return rows


def process_bulk_pdf_edits(
    template_pdf_path: str,
    data_file_path: str,
    output_dir: str,
    field_mappings: Optional[Dict[str, str]] = None,
    send_email_toggle: bool = False,
    email_column_name: Optional[str] = None,
    email_subject: str = "Your Document Offer Letter",
    email_body: str = "Dear Candidate,\n\nPlease find attached your offer letter PDF.\n\nBest Regards,\nHR Team",
    smtp_config: Optional[Dict[str, Any]] = None,
    progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None
) -> Dict[str, Any]:
    """Generates bulk PDFs for each row in the data file using optional field mappings and sends emails if enabled."""
    load_dotenv_if_exists()
    os.makedirs(output_dir, exist_ok=True)
    data_rows = parse_data_file(data_file_path)

    if not data_rows:
        return {
            "success": False,
            "message": "Data file is empty or contains no valid rows.",
            "generated_count": 0
        }

    generated_pdfs = []
    failed_rows = []
    sent_emails_count = 0
    failed_emails_count = 0
    email_errors = []
    zip_path = os.path.join(output_dir, "bulk_edited_pdfs.zip")
    used_filenames = set()

    smtp_cfg = smtp_config or {}

    # Resolve SMTP credentials — UI fields first, then env vars as fallback
    smtp_sender_email = (smtp_cfg.get("sender_email") or "").strip() or os.environ.get("SMTP_SENDER_EMAIL", "").strip()
    smtp_sender_password = (smtp_cfg.get("sender_password") or "").strip() or os.environ.get("SMTP_SENDER_PASSWORD", "").strip()
    smtp_host = (smtp_cfg.get("host") or "").strip() or os.environ.get("SMTP_HOST", "smtp.hostinger.com").strip()
    
    port_raw = smtp_cfg.get("port", 0)
    try:
        smtp_port = int(port_raw or os.environ.get("SMTP_PORT", 0) or 465)
    except Exception:
        smtp_port = 465

    batch_sender: Optional[SMTPBatchSender] = None

    # Pre-flight check: if email is enabled, verify credentials and test connection BEFORE processing
    if send_email_toggle:
        if not smtp_sender_email or not smtp_sender_password:
            return {
                "success": False,
                "message": (
                    "Email dispatch is enabled but SMTP credentials are missing. "
                    "Please fill in Sender Email and Password in the Email Dispatch section, "
                    "or set SMTP_SENDER_EMAIL and SMTP_SENDER_PASSWORD environment variables in .env file."
                ),
                "generated_count": 0
            }
        if not email_column_name:
            return {
                "success": False,
                "message": "Email dispatch is enabled but no recipient email column was selected.",
                "generated_count": 0
            }

        # Initialize reusable batch sender & perform pre-flight connection test
        batch_sender = SMTPBatchSender(
            host=smtp_host,
            port=smtp_port,
            sender_email=smtp_sender_email,
            sender_password=smtp_sender_password
        )
        preflight = batch_sender.connect()
        if not preflight.get("success"):
            return {
                "success": False,
                "message": f"Pre-flight Email Verification Failed: {preflight.get('error')}. Please verify sender credentials before generating bulk PDFs.",
                "generated_count": 0
            }

    # Analyze base template once
    template_analysis = analyze_pdf(template_pdf_path)

    total_rows = len(data_rows)
    try:
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for idx, row_dict in enumerate(data_rows, start=1):
                recipient_email_val = _find_col_case_insensitive(row_dict, email_column_name) if (send_email_toggle and email_column_name) else None
                recip_label = f" ({recipient_email_val})" if recipient_email_val else ""

                if progress_callback:
                    progress_callback({
                        "current_row": idx,
                        "total_rows": total_rows,
                        "progress_percent": int(((idx - 0.5) / total_rows) * 100),
                        "status_step": f"Generating PDF & email for candidate {idx} of {total_rows}{recip_label}",
                        "next_step": f"Row {idx + 1}: {data_rows[idx].get('name', 'Next candidate')}" if idx < total_rows else "Finalizing ZIP package",
                        "sent_emails_count": sent_emails_count,
                        "failed_emails_count": failed_emails_count,
                        "generated_count": len(generated_pdfs)
                    })
                # Construct changes map using field_mappings if supplied
                row_changes = {}
                if field_mappings:
                    for pdf_field, col_header in field_mappings.items():
                        val = _find_col_case_insensitive(row_dict, col_header)
                        if val is not None:
                            row_changes[pdf_field] = val
                else:
                    row_changes = row_dict

                if not row_changes:
                    row_changes = row_dict

                # Determine output PDF filename based on Ref ID or Name column
                ref_id_val = None
                for key, val in row_changes.items():
                    k_lower = str(key).lower()
                    v_str = str(val)
                    if ("ref" in k_lower or "id" in k_lower or "code" in k_lower or v_str.startswith("ALG-")) and v_str:
                        ref_id_val = v_str
                        break

                if not ref_id_val:
                    for key, val in row_dict.items():
                        if ("ref" in str(key).lower() or "id" in str(key).lower() or str(val).startswith("ALG-")) and str(val):
                            ref_id_val = str(val)
                            break

                if not ref_id_val:
                    name_val = row_changes.get("name") or row_changes.get("Name") or row_changes.get("NAME")
                    ref_id_val = name_val if name_val else f"row_{idx}"

                safe_basename = sanitize_filename(ref_id_val)
                out_pdf_name = f"{safe_basename}.pdf"
                if out_pdf_name in used_filenames:
                    out_pdf_name = f"{safe_basename}_{idx}.pdf"
                used_filenames.add(out_pdf_name)

                out_pdf_path = os.path.join(output_dir, out_pdf_name)

                # Build edit plan for this row
                plan = build_edit_plan(template_analysis, row_changes)

                if not plan.get("success"):
                    failed_rows.append({
                        "row": idx,
                        "changes": row_changes,
                        "reason": plan.get("message", "Edit plan generation failed.")
                    })
                    continue

                # Mutate PDF
                edit_res = edit_native_text_pdf(template_pdf_path, out_pdf_path, plan["operations"])

                if edit_res.get("success"):
                    val_res = validate_pdf_edit(template_pdf_path, out_pdf_path, plan["operations"])
                    zipf.write(out_pdf_path, arcname=out_pdf_name)

                    email_status = None
                    if send_email_toggle and email_column_name and batch_sender:
                        recipient_email = _find_col_case_insensitive(row_dict, email_column_name)
                        if recipient_email and "@" in recipient_email:
                            email_res = batch_sender.send_one(
                                to_email=recipient_email,
                                subject=email_subject,
                                body_text=email_body,
                                pdf_path=out_pdf_path
                            )
                            email_status = email_res
                            if email_res.get("success"):
                                sent_emails_count += 1
                            else:
                                failed_emails_count += 1
                                email_errors.append({
                                    "row": idx,
                                    "recipient": recipient_email,
                                    "error": email_res.get("error", "Unknown SMTP error")
                                })
                        else:
                            failed_emails_count += 1
                            email_errors.append({
                                "row": idx,
                                "recipient": recipient_email or "(empty)",
                                "error": f"No valid email address found in column '{email_column_name}' for this row."
                            })

                    generated_pdfs.append({
                        "row": idx,
                        "filename": out_pdf_name,
                        "filepath": out_pdf_path,
                        "validation": val_res,
                        "email_status": email_status
                    })
                else:
                    failed_rows.append({
                        "row": idx,
                        "changes": row_changes,
                        "reason": "PDF native text mutation failed."
                    })

                if progress_callback:
                    progress_callback({
                        "current_row": idx,
                        "total_rows": total_rows,
                        "progress_percent": int((idx / total_rows) * 100),
                        "status_step": f"Completed candidate {idx} of {total_rows}{recip_label}",
                        "next_step": f"Row {idx + 1}: {data_rows[idx].get('name', 'Next candidate')}" if idx < total_rows else "Finalizing ZIP archive",
                        "sent_emails_count": sent_emails_count,
                        "failed_emails_count": failed_emails_count,
                        "generated_count": len(generated_pdfs)
                    })
    finally:
        if batch_sender:
            batch_sender.close()

    return {
        "success": len(generated_pdfs) > 0,
        "zip_path": zip_path,
        "total_rows": len(data_rows),
        "generated_count": len(generated_pdfs),
        "failed_count": len(failed_rows),
        "sent_emails_count": sent_emails_count,
        "failed_emails_count": failed_emails_count,
        "email_errors": email_errors,
        "generated_pdfs": generated_pdfs,
        "failed_rows": failed_rows
    }

