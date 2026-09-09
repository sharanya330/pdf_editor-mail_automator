"""FastAPI API Routes for PDF Analysis, Single Editing, Bulk Editing, Templates, and File Download."""

import os
import uuid
import json
from typing import Dict, Any, Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse

from pdf.analyzer import analyze_pdf
from pdf.field_resolver import parse_natural_language_instruction, build_edit_plan
from pdf.forms import edit_acroform_pdf
from pdf.text_editor import edit_native_text_pdf
from pdf.ocr_editor import edit_scanned_pdf
from pdf.validator import validate_pdf_edit
from pdf.template_manager import register_template, get_template, load_templates
from pdf.bulk_processor import process_bulk_pdf_edits, parse_data_file
from pdf.email_sender import send_email_with_attachment, send_email_with_pdf_attachment, test_smtp_connection, load_dotenv_if_exists
from jpeg.analyzer import analyze_jpeg
from jpeg.editor import edit_jpeg
from jpeg.bulk_processor import process_bulk_jpeg_edits

load_dotenv_if_exists()

import tempfile
import threading

router = APIRouter(prefix="/pdf", tags=["PDF Engine"])
jpeg_router = APIRouter(prefix="/jpeg", tags=["JPEG Engine"])


TEMP_DIR = os.path.join(tempfile.gettempdir(), "pdf_editor_temp")
os.makedirs(TEMP_DIR, exist_ok=True)

# File-based job store — survives process restarts (in-memory dict would lose jobs on Railway restart)
JOBS_DIR = os.path.join(tempfile.gettempdir(), "pdf_editor_jobs")
os.makedirs(JOBS_DIR, exist_ok=True)


def _write_job(job_id: str, data: Dict[str, Any]) -> None:
    """Persist job state to a JSON file."""
    job_path = os.path.join(JOBS_DIR, f"{job_id}.json")
    with open(job_path, "w", encoding="utf-8") as f:
        json.dump(data, f)


def _read_job(job_id: str) -> Optional[Dict[str, Any]]:
    """Read job state from disk. Returns None if not found."""
    job_path = os.path.join(JOBS_DIR, f"{job_id}.json")
    if not os.path.exists(job_path):
        return None
    try:
        with open(job_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def cleanup_file(path: str):
    """Background task to remove temporary files."""
    if os.path.exists(path):
        try:
            os.remove(path)
        except Exception:
            pass


@router.get("/favicon.ico")
async def favicon():
    return JSONResponse(status_code=204, content={})


@router.get("/smtp-info")
async def api_smtp_info() -> Dict[str, Any]:
    """Returns detected default SMTP configuration from environment or .env file."""
    load_dotenv_if_exists()
    sender = os.environ.get("SMTP_SENDER_EMAIL", "").strip()
    host = os.environ.get("SMTP_HOST", "smtp.hostinger.com").strip()
    try:
        port = int(os.environ.get("SMTP_PORT", 0) or 465)
    except Exception:
        port = 465
    has_pass = bool(os.environ.get("SMTP_SENDER_PASSWORD", "").strip())
    return {
        "has_credentials": bool(sender and has_pass),
        "sender_email": sender,
        "host": host,
        "port": port
    }


@router.post("/test-smtp")
async def api_test_smtp(
    sender_email: Optional[str] = Form(None),
    sender_password: Optional[str] = Form(None),
    smtp_host: Optional[str] = Form(None),
    smtp_port: Optional[int] = Form(None),
    test_recipient: Optional[str] = Form("test@algoryx.in")
) -> JSONResponse:
    """Tests connection & authentication to an SMTP server and dispatches a test email."""
    res = test_smtp_connection(
        smtp_host=smtp_host or "",
        smtp_port=int(smtp_port or 0),
        sender_email=sender_email or "",
        sender_password=sender_password or "",
        test_recipient=test_recipient or "test@algoryx.in"
    )
    status_code = 200 if res.get("success") else 400
    return JSONResponse(status_code=status_code, content=res)




@router.post("/analyze")
async def api_analyze_pdf(file: UploadFile = File(...)) -> Dict[str, Any]:
    """Analyzes uploaded PDF and returns structural breakdown."""
    file_id = str(uuid.uuid4())
    temp_path = os.path.join(TEMP_DIR, f"input_{file_id}.pdf")

    try:
        content = await file.read()
        with open(temp_path, "wb") as f:
            f.write(content)

        analysis = analyze_pdf(temp_path)
        return analysis
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"PDF analysis failed: {str(e)}")
    finally:
        cleanup_file(temp_path)


@router.post("/parse-columns")
async def api_parse_columns(file: UploadFile = File(...)) -> Dict[str, Any]:
    """Reads headers/column names from an uploaded Excel or CSV file."""
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in (".csv", ".xlsx", ".xls"):
        raise HTTPException(status_code=400, detail="Data file must be a .csv or .xlsx file.")

    file_id = str(uuid.uuid4())
    temp_path = os.path.join(TEMP_DIR, f"cols_{file_id}{ext}")
    try:
        content = await file.read()
        with open(temp_path, "wb") as f:
            f.write(content)

        rows = parse_data_file(temp_path)
        headers = list(rows[0].keys()) if rows else []
        return {
            "success": True,
            "filename": file.filename,
            "columns": headers,
            "sample_row": rows[0] if rows else {}
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse data file columns: {str(e)}")
    finally:
        cleanup_file(temp_path)


@router.post("/edit")
async def api_edit_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    changes_json: Optional[str] = Form(None),
    instruction: Optional[str] = Form(None),
    template_id: Optional[str] = Form(None),
    send_email: bool = Form(False),
    recipient_email: Optional[str] = Form(None),
    email_subject: Optional[str] = Form("Your Edited PDF Document"),
    email_body: Optional[str] = Form("Hello,\n\nPlease find attached your edited PDF document.\n\nBest Regards,"),
    smtp_json: Optional[str] = Form(None)
) -> Dict[str, Any]:
    """Edits requested text fields in uploaded PDF while preserving all non-target content."""
    file_id = str(uuid.uuid4())
    input_path = os.path.join(TEMP_DIR, f"input_{file_id}.pdf")
    output_filename = f"edited_{file_id}.pdf"
    output_path = os.path.join(TEMP_DIR, output_filename)

    try:
        content = await file.read()
        with open(input_path, "wb") as f:
            f.write(content)

        # Parse requested changes
        changes = {}
        if changes_json:
            try:
                changes = json.loads(changes_json)
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid changes_json format. Must be valid JSON object.")
        elif instruction:
            changes = parse_natural_language_instruction(instruction)

        if not changes and not template_id:
            raise HTTPException(status_code=400, detail="No field changes or instruction provided.")

        # 1. Analyze input PDF
        analysis = analyze_pdf(input_path)
        pdf_mode = analysis["mode"]

        # 2. Build Edit Plan
        if template_id:
            tpl = get_template(template_id)
            if not tpl:
                raise HTTPException(status_code=404, detail=f"Template '{template_id}' not found.")
            operations = []
            for fk, nv in changes.items():
                if fk in tpl["fields"]:
                    fmeta = tpl["fields"][fk]
                    operations.append({
                        "field": fk,
                        "target_type": "native_text",
                        "page": fmeta.get("page", 0),
                        "bbox": fmeta["bbox"],
                        "font": fmeta.get("font", "helv"),
                        "size": fmeta.get("size", 12.0),
                        "old_value": "",
                        "new_value": nv,
                        "span": {"bbox": fmeta["bbox"], "font": fmeta.get("font", "helv"), "size": fmeta.get("size", 12.0)}
                    })
            plan = {"success": True, "operations": operations, "mode": pdf_mode}
        else:
            plan = build_edit_plan(analysis, changes)

        if not plan.get("success"):
            cleanup_file(input_path)
            return plan

        operations = plan["operations"]

        # 3. Perform Targeted PDF Mutation based on PDF Mode
        if pdf_mode == "MODE_A_ACROFORM":
            mutate_res = edit_acroform_pdf(input_path, output_path, operations)
        elif pdf_mode == "MODE_B_NATIVE_TEXT":
            mutate_res = edit_native_text_pdf(input_path, output_path, operations)
        elif pdf_mode == "MODE_C_SCANNED":
            mutate_res = edit_scanned_pdf(input_path, output_path, operations)
        else:
            mutate_res = edit_native_text_pdf(input_path, output_path, operations)

        if not mutate_res.get("success"):
            cleanup_file(input_path)
            return {
                "success": False,
                "reason": mutate_res.get("error", "Targeted PDF mutation failed."),
                "requires_manual_review": True
            }

        # 4. Post-Edit Validation
        validation = validate_pdf_edit(input_path, output_path, operations)

        if not validation["passed"]:
            cleanup_file(input_path)
            cleanup_file(output_path)
            return {
                "success": False,
                "reason": f"Validation failed: {', '.join(validation['failures'])}",
                "validation": validation,
                "requires_manual_review": True
            }

        email_status = None
        if send_email:
            if not recipient_email or "@" not in recipient_email:
                email_status = {
                    "success": False,
                    "error": "Invalid or missing recipient email address.",
                    "recipient": recipient_email or ""
                }
            else:
                smtp_cfg = {}
                if smtp_json:
                    try:
                        smtp_cfg = json.loads(smtp_json)
                    except Exception:
                        pass
                
                sender_email = (smtp_cfg.get("sender_email") or "").strip() or None
                sender_password = (smtp_cfg.get("sender_password") or "").strip() or None
                host = (smtp_cfg.get("host") or "").strip() or None
                port_raw = smtp_cfg.get("port", 0)
                try:
                    port = int(port_raw) if port_raw else None
                except Exception:
                    port = None

                email_res = send_email_with_pdf_attachment(
                    to_email=recipient_email.strip(),
                    subject=email_subject or "Your Edited PDF Document",
                    body_text=email_body or "Please find attached your edited PDF document.",
                    attachment_pdf_path=output_path,
                    smtp_host=host,
                    smtp_port=port,
                    sender_email=sender_email,
                    sender_password=sender_password
                )
                email_status = email_res

        background_tasks.add_task(cleanup_file, input_path)

        return {
            "success": True,
            "mode": pdf_mode,
            "output_file": output_filename,
            "download_url": f"/pdf/download/{output_filename}",
            "validation": validation,
            "email_status": email_status
        }

    except HTTPException:
        cleanup_file(input_path)
        raise
    except Exception as e:
        cleanup_file(input_path)
        cleanup_file(output_path)
        return {
            "success": False,
            "reason": f"Internal editing error: {str(e)}",
            "requires_manual_review": True
        }


@router.post("/edit-bulk")
async def api_edit_pdf_bulk(
    background_tasks: BackgroundTasks,
    pdf_file: UploadFile = File(...),
    data_file: UploadFile = File(...),
    mappings_json: Optional[str] = Form(None),
    send_email: bool = Form(False),
    email_column: Optional[str] = Form(None),
    email_subject: Optional[str] = Form("Your Internship Offer Letter"),
    email_body: Optional[str] = Form("Dear Candidate,\n\nPlease find attached your internship offer letter.\n\nBest Regards,\nHR Team"),
    smtp_json: Optional[str] = Form(None)
) -> Dict[str, Any]:
    """Accepts bulk PDF job, saves files, starts background processing, returns job_id immediately."""
    bulk_id = str(uuid.uuid4())
    pdf_temp_path = os.path.join(TEMP_DIR, f"template_{bulk_id}.pdf")

    data_ext = os.path.splitext(data_file.filename)[1].lower()
    if data_ext not in (".csv", ".xlsx", ".xls"):
        raise HTTPException(status_code=400, detail="Data file must be a .csv or .xlsx file.")

    data_temp_path = os.path.join(TEMP_DIR, f"data_{bulk_id}{data_ext}")
    bulk_out_dir = os.path.join(TEMP_DIR, f"bulk_out_{bulk_id}")

    pdf_content = await pdf_file.read()
    with open(pdf_temp_path, "wb") as f:
        f.write(pdf_content)

    data_content = await data_file.read()
    with open(data_temp_path, "wb") as f:
        f.write(data_content)

    field_mappings = None
    if mappings_json:
        try:
            field_mappings = json.loads(mappings_json)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid mappings_json format.")

    smtp_config = None
    if smtp_json:
        try:
            smtp_config = json.loads(smtp_json)
        except Exception:
            pass

    # Register job as pending in file store
    _write_job(bulk_id, {"status": "processing", "job_id": bulk_id})

    def _run_bulk():
        def _on_progress(prog_data: Dict[str, Any]):
            _write_job(bulk_id, {
                "status": "processing",
                "job_id": bulk_id,
                "current_row": prog_data.get("current_row", 0),
                "total_rows": prog_data.get("total_rows", 0),
                "progress_percent": prog_data.get("progress_percent", 0),
                "status_step": prog_data.get("status_step", ""),
                "next_step": prog_data.get("next_step", ""),
                "sent_emails_count": prog_data.get("sent_emails_count", 0),
                "failed_emails_count": prog_data.get("failed_emails_count", 0),
                "generated_count": prog_data.get("generated_count", 0)
            })

        try:
            res = process_bulk_pdf_edits(
                pdf_temp_path,
                data_temp_path,
                bulk_out_dir,
                field_mappings=field_mappings,
                send_email_toggle=send_email,
                email_column_name=email_column,
                email_subject=email_subject or "Your Internship Offer Letter",
                email_body=email_body or "Dear Candidate,\n\nPlease find attached your offer letter.",
                smtp_config=smtp_config,
                progress_callback=_on_progress
            )
            if not res.get("success"):
                _write_job(bulk_id, {"status": "failed", "job_id": bulk_id, "error": res.get("message", "Bulk generation failed.")})
                return

            zip_filename = f"bulk_{bulk_id}.zip"
            zip_dest_path = os.path.join(TEMP_DIR, zip_filename)
            os.rename(res["zip_path"], zip_dest_path)

            _write_job(bulk_id, {
                "status": "done",
                "job_id": bulk_id,
                "zip_filename": zip_filename,
                "download_url": f"/pdf/download-zip/{zip_filename}",
                "total_rows": res["total_rows"],
                "generated_count": res["generated_count"],
                "failed_count": res["failed_count"],
                "sent_emails_count": res.get("sent_emails_count", 0),
                "failed_emails_count": res.get("failed_emails_count", 0),
                "email_errors": res.get("email_errors", []),
                "generated_pdfs": res["generated_pdfs"],
                "failed_rows": res["failed_rows"]
            })
        except Exception as e:
            _write_job(bulk_id, {"status": "failed", "job_id": bulk_id, "error": str(e)})
        finally:
            cleanup_file(pdf_temp_path)
            cleanup_file(data_temp_path)

    t = threading.Thread(target=_run_bulk, daemon=True)
    t.start()

    return {"success": True, "status": "processing", "job_id": bulk_id, "poll_url": f"/pdf/bulk-status/{bulk_id}"}


@router.get("/bulk-status/{job_id}")
async def api_bulk_status(job_id: str) -> Dict[str, Any]:
    """Returns current status of a background bulk PDF job (reads from file-based store)."""
    job = _read_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found. It may have expired or the server restarted before saving it.")
    return job


@router.get("/download/{file_name}")
async def api_download_pdf(file_name: str):
    """Serves modified output PDF for download."""
    file_path = os.path.join(TEMP_DIR, file_name)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found.")
    return FileResponse(file_path, media_type="application/pdf", filename=file_name)


@router.get("/download-zip/{zip_name}")
async def api_download_zip(zip_name: str):
    """Serves generated bulk ZIP archive for download."""
    file_path = os.path.join(TEMP_DIR, zip_name)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="ZIP file not found.")
    return FileResponse(file_path, media_type="application/zip", filename=zip_name)


@router.get("/templates")
async def api_list_templates():
    """Lists all registered templates."""
    return load_templates()


@router.post("/templates")
async def api_register_template(template_id: str, fields: Dict[str, Any]):
    """Registers a new PDF template configuration."""
    return register_template(template_id, fields)


# ==========================================
# JPEG EDITOR ROUTE HANDLERS
# ==========================================

@jpeg_router.post("/analyze")
async def api_analyze_jpeg(file: UploadFile = File(...)) -> Dict[str, Any]:
    """Analyzes uploaded JPEG image to detect text bounding boxes, colors, and free-space candidate areas."""
    temp_id = str(uuid.uuid4())
    ext = ".jpg"
    if file.filename and file.filename.lower().endswith(".png"):
        ext = ".png"

    input_path = os.path.join(TEMP_DIR, f"jpeg_analyze_{temp_id}{ext}")
    try:
        content = await file.read()
        with open(input_path, "wb") as f:
            f.write(content)

        res = analyze_jpeg(input_path)
        return res
    finally:
        cleanup_file(input_path)


@jpeg_router.post("/edit")
async def api_edit_jpeg(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    replacements_json: Optional[str] = Form(None),
    insertions_json: Optional[str] = Form(None),
    send_email: bool = Form(False),
    recipient_email: Optional[str] = Form(None),
    email_subject: Optional[str] = Form("Your Edited Document"),
    email_body: Optional[str] = Form("Hello,\n\nPlease find attached your customized document.\n\nBest Regards,"),
    smtp_json: Optional[str] = Form(None)
) -> Dict[str, Any]:
    """Edits text regions and inserts free-space text values into an uploaded JPEG image with optional email delivery."""
    temp_id = str(uuid.uuid4())
    ext = ".jpg"
    if file.filename and file.filename.lower().endswith(".png"):
        ext = ".png"

    input_path = os.path.join(TEMP_DIR, f"jpeg_in_{temp_id}{ext}")
    output_filename = f"edited_jpeg_{temp_id[:8]}{ext}"
    output_path = os.path.join(TEMP_DIR, output_filename)

    try:
        content = await file.read()
        with open(input_path, "wb") as f:
            f.write(content)

        replacements = json.loads(replacements_json) if replacements_json else []
        insertions = json.loads(insertions_json) if insertions_json else []

        edit_res = edit_jpeg(input_path, output_path, replacements=replacements, insertions=insertions)
        if not edit_res.get("success"):
            raise HTTPException(status_code=500, detail=edit_res.get("error", "JPEG edit failed."))

        email_status = None
        if send_email:
            if not recipient_email or "@" not in recipient_email:
                email_status = {
                    "success": False,
                    "error": "Invalid or missing recipient email address.",
                    "recipient": recipient_email or ""
                }
            else:
                smtp_cfg = json.loads(smtp_json) if smtp_json else {}
                sender_email = (smtp_cfg.get("sender_email") or "").strip() or None
                sender_password = (smtp_cfg.get("sender_password") or "").strip() or None
                host = (smtp_cfg.get("host") or "").strip() or None
                port_raw = smtp_cfg.get("port", 0)
                try:
                    port = int(port_raw) if port_raw else None
                except Exception:
                    port = None

                email_status = send_email_with_attachment(
                    to_email=recipient_email.strip(),
                    subject=email_subject or "Your Edited Document",
                    body_text=email_body or "Please find attached your customized document.",
                    attachment_path=output_path,
                    smtp_host=host,
                    smtp_port=port,
                    sender_email=sender_email,
                    sender_password=sender_password
                )

        background_tasks.add_task(cleanup_file, input_path)

        return {
            "success": True,
            "output_file": output_filename,
            "download_url": f"/jpeg/download/{output_filename}",
            "applied_replacements": edit_res.get("applied_replacements", 0),
            "applied_insertions": edit_res.get("applied_insertions", 0),
            "email_status": email_status
        }
    except Exception as e:
        cleanup_file(input_path)
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))


@jpeg_router.post("/edit-bulk")
async def api_edit_jpeg_bulk(
    jpeg_file: UploadFile = File(...),
    data_file: UploadFile = File(...),
    mappings_json: str = Form(...),
    send_email: bool = Form(False),
    email_column: Optional[str] = Form(None),
    email_subject: Optional[str] = Form(None),
    email_body: Optional[str] = Form(None),
    smtp_json: Optional[str] = Form(None)
) -> Dict[str, Any]:
    """Bulk processes JPEG image template against Excel/CSV data rows in the background."""
    bulk_id = str(uuid.uuid4())
    jpeg_ext = ".jpg"
    if jpeg_file.filename and jpeg_file.filename.lower().endswith(".png"):
        jpeg_ext = ".png"

    jpeg_temp_path = os.path.join(TEMP_DIR, f"bulk_template_{bulk_id}{jpeg_ext}")
    data_ext = os.path.splitext(data_file.filename or "")[1] or ".xlsx"
    data_temp_path = os.path.join(TEMP_DIR, f"bulk_data_{bulk_id}{data_ext}")
    bulk_out_dir = os.path.join(TEMP_DIR, f"bulk_jpeg_out_{bulk_id}")

    with open(jpeg_temp_path, "wb") as f:
        f.write(await jpeg_file.read())

    with open(data_temp_path, "wb") as f:
        f.write(await data_file.read())

    try:
        mappings = json.loads(mappings_json)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid mappings_json format.")

    smtp_config = json.loads(smtp_json) if smtp_json else None

    _write_job(bulk_id, {"status": "processing", "job_id": bulk_id})

    def _run_bulk_jpeg():
        def _on_progress(prog_data: Dict[str, Any]):
            _write_job(bulk_id, {
                "status": "processing",
                "job_id": bulk_id,
                "current_row": prog_data.get("current_row", 0),
                "total_rows": prog_data.get("total_rows", 0),
                "progress_percent": prog_data.get("progress_percent", 0),
                "status_step": prog_data.get("status_step", ""),
                "next_step": prog_data.get("next_step", ""),
                "sent_emails_count": prog_data.get("sent_emails_count", 0),
                "failed_emails_count": prog_data.get("failed_emails_count", 0),
                "generated_count": prog_data.get("generated_count", 0)
            })

        try:
            res = process_bulk_jpeg_edits(
                jpeg_template_path=jpeg_temp_path,
                data_file_path=data_temp_path,
                output_dir=bulk_out_dir,
                mapping_config=mappings,
                email_column_name=email_column if send_email else None,
                email_subject=email_subject or "Your Document",
                email_body=email_body or "Please find attached your customized document.",
                smtp_config=smtp_config,
                progress_callback=_on_progress
            )

            if not res.get("success"):
                _write_job(bulk_id, {"status": "failed", "job_id": bulk_id, "error": res.get("message", "Bulk JPEG generation failed.")})
                return

            zip_filename = res.get("zip_file")
            _write_job(bulk_id, {
                "status": "done",
                "job_id": bulk_id,
                "zip_filename": zip_filename,
                "download_url": f"/jpeg/download/{zip_filename}",
                "total_rows": res.get("total_rows", 0),
                "generated_count": res.get("generated_count", 0),
                "sent_emails_count": res.get("sent_emails_count", 0),
                "failed_emails_count": res.get("failed_emails_count", 0),
                "errors": res.get("errors", [])
            })
        except Exception as e:
            _write_job(bulk_id, {"status": "failed", "job_id": bulk_id, "error": str(e)})
        finally:
            cleanup_file(jpeg_temp_path)
            cleanup_file(data_temp_path)

    t = threading.Thread(target=_run_bulk_jpeg, daemon=True)
    t.start()

    return {"success": True, "status": "processing", "job_id": bulk_id, "poll_url": f"/jpeg/bulk-status/{bulk_id}"}


@jpeg_router.get("/bulk-status/{job_id}")
async def api_jpeg_bulk_status(job_id: str) -> Dict[str, Any]:
    """Returns current status of a background bulk JPEG job."""
    job = _read_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    return job


@jpeg_router.get("/download/{file_name}")
async def api_download_jpeg(file_name: str):
    """Serves modified JPEG file or ZIP archive for download."""
    file_path = os.path.join(TEMP_DIR, file_name)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found.")

    media_type = "application/zip" if file_name.endswith(".zip") else "image/jpeg"
    return FileResponse(file_path, media_type=media_type, filename=file_name)


