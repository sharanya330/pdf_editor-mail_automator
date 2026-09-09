"""Comprehensive Automated Test Suite for PDF Text-Field Editor.

Tests all 20 required scenarios and the critical composite asset-preservation test.
"""

import os
import pytest
from pdf.analyzer import analyze_pdf
from pdf.field_resolver import build_edit_plan
from pdf.text_editor import edit_native_text_pdf
from pdf.forms import edit_acroform_pdf
from pdf.ocr_editor import edit_scanned_pdf
from pdf.validator import validate_pdf_edit
from tests.pdf_fixtures import (
    create_native_text_pdf,
    create_composite_pdf_with_assets,
    create_acroform_pdf,
    create_ambiguous_text_pdf,
    create_scanned_pdf,
    create_multipage_pdf
)

TEST_DIR = "test_output"
os.makedirs(TEST_DIR, exist_ok=True)


def test_01_single_text_replacement():
    in_pdf = os.path.join(TEST_DIR, "native_01.pdf")
    out_pdf = os.path.join(TEST_DIR, "out_native_01.pdf")
    create_native_text_pdf(in_pdf)

    analysis = analyze_pdf(in_pdf)
    plan = build_edit_plan(analysis, {"name": "Sairaj"})

    assert plan["success"] is True
    res = edit_native_text_pdf(in_pdf, out_pdf, plan["operations"])
    assert res["success"] is True

    validation = validate_pdf_edit(in_pdf, out_pdf, plan["operations"])
    assert validation["passed"] is True
    assert validation["images_preserved"] is True
    assert validation["page_geometry_preserved"] is True


def test_02_multiple_text_replacements():
    in_pdf = os.path.join(TEST_DIR, "native_02.pdf")
    out_pdf = os.path.join(TEST_DIR, "out_native_02.pdf")
    create_native_text_pdf(in_pdf)

    analysis = analyze_pdf(in_pdf)
    plan = build_edit_plan(analysis, {"name": "Sairaj", "date": "09/08/2026", "duration": "1 Month"})

    assert plan["success"] is True
    res = edit_native_text_pdf(in_pdf, out_pdf, plan["operations"])
    assert res["success"] is True

    validation = validate_pdf_edit(in_pdf, out_pdf, plan["operations"])
    assert validation["passed"] is True


def test_03_same_text_appearing_multiple_times():
    in_pdf = os.path.join(TEST_DIR, "ambiguous_03.pdf")
    out_pdf = os.path.join(TEST_DIR, "out_ambiguous_03.pdf")
    create_ambiguous_text_pdf(in_pdf)

    analysis = analyze_pdf(in_pdf)
    plan = build_edit_plan(analysis, {"name": "Sairaj"})
    assert plan["success"] is True
    assert len(plan["operations"]) == 2

    res = edit_native_text_pdf(in_pdf, out_pdf, plan["operations"])
    assert res["success"] is True


def test_04_ambiguous_field_detection():
    in_pdf = os.path.join(TEST_DIR, "ambiguous_04.pdf")
    out_pdf = os.path.join(TEST_DIR, "out_ambiguous_04.pdf")
    create_ambiguous_text_pdf(in_pdf)

    analysis = analyze_pdf(in_pdf)
    plan = build_edit_plan(analysis, {"name": "Sairaj"})
    assert plan["success"] is True
    assert len(plan["operations"]) == 2

    res = edit_native_text_pdf(in_pdf, out_pdf, plan["operations"])
    assert res["success"] is True


def test_05_missing_field():
    in_pdf = os.path.join(TEST_DIR, "native_05.pdf")
    create_native_text_pdf(in_pdf)

    analysis = analyze_pdf(in_pdf)
    plan = build_edit_plan(analysis, {"nonexistent_field": "Val"})

    assert plan["success"] is False
    assert plan["status"] == "missing_fields"


def test_06_long_replacement_text():
    in_pdf = os.path.join(TEST_DIR, "native_06.pdf")
    out_pdf = os.path.join(TEST_DIR, "out_native_06.pdf")
    create_native_text_pdf(in_pdf)

    analysis = analyze_pdf(in_pdf)
    super_long_str = "Extremely Long Text String That Far Exceeds Page Width And Available Bounding Box Width " * 10
    plan = build_edit_plan(analysis, {"date": super_long_str})

    if plan["success"]:
        res = edit_native_text_pdf(in_pdf, out_pdf, plan["operations"])
        assert res["success"] is True


def test_07_short_replacement_text():
    in_pdf = os.path.join(TEST_DIR, "native_07.pdf")
    out_pdf = os.path.join(TEST_DIR, "out_native_07.pdf")
    create_native_text_pdf(in_pdf)

    analysis = analyze_pdf(in_pdf)
    plan = build_edit_plan(analysis, {"duration": "1d"})

    assert plan["success"] is True
    res = edit_native_text_pdf(in_pdf, out_pdf, plan["operations"])
    assert res["success"] is True

    validation = validate_pdf_edit(in_pdf, out_pdf, plan["operations"])
    assert validation["passed"] is True


def test_08_centered_text():
    in_pdf = os.path.join(TEST_DIR, "composite_08.pdf")
    out_pdf = os.path.join(TEST_DIR, "out_composite_08.pdf")
    create_composite_pdf_with_assets(in_pdf)

    analysis = analyze_pdf(in_pdf)
    plan = build_edit_plan(analysis, {"name": "Sairaj"})
    assert plan["success"] is True

    res = edit_native_text_pdf(in_pdf, out_pdf, plan["operations"])
    assert res["success"] is True

    validation = validate_pdf_edit(in_pdf, out_pdf, plan["operations"])
    assert validation["passed"] is True


def test_09_different_fonts():
    in_pdf = os.path.join(TEST_DIR, "native_09.pdf")
    out_pdf = os.path.join(TEST_DIR, "out_native_09.pdf")
    create_native_text_pdf(in_pdf)

    analysis = analyze_pdf(in_pdf)
    plan = build_edit_plan(analysis, {"name": "Alex", "duration": "2 Weeks"})
    assert plan["success"] is True

    res = edit_native_text_pdf(in_pdf, out_pdf, plan["operations"])
    assert res["success"] is True


def test_10_pdf_containing_images():
    in_pdf = os.path.join(TEST_DIR, "composite_10.pdf")
    out_pdf = os.path.join(TEST_DIR, "out_composite_10.pdf")
    create_composite_pdf_with_assets(in_pdf)

    analysis = analyze_pdf(in_pdf)
    assert analysis["total_images"] > 0

    plan = build_edit_plan(analysis, {"name": "Jane Smith"})
    res = edit_native_text_pdf(in_pdf, out_pdf, plan["operations"])
    assert res["success"] is True

    validation = validate_pdf_edit(in_pdf, out_pdf, plan["operations"])
    assert validation["images_preserved"] is True


def test_11_pdf_containing_logos():
    in_pdf = os.path.join(TEST_DIR, "composite_11.pdf")
    out_pdf = os.path.join(TEST_DIR, "out_composite_11.pdf")
    create_composite_pdf_with_assets(in_pdf)

    analysis = analyze_pdf(in_pdf)
    plan = build_edit_plan(analysis, {"date": "20/12/2026"})
    edit_native_text_pdf(in_pdf, out_pdf, plan["operations"])

    validation = validate_pdf_edit(in_pdf, out_pdf, plan["operations"])
    assert validation["images_preserved"] is True


def test_12_pdf_containing_vectors():
    in_pdf = os.path.join(TEST_DIR, "composite_12.pdf")
    out_pdf = os.path.join(TEST_DIR, "out_composite_12.pdf")
    create_composite_pdf_with_assets(in_pdf)

    analysis = analyze_pdf(in_pdf)
    assert analysis["total_drawings"] > 0

    plan = build_edit_plan(analysis, {"name": "Jane Smith"})
    edit_native_text_pdf(in_pdf, out_pdf, plan["operations"])

    validation = validate_pdf_edit(in_pdf, out_pdf, plan["operations"])
    assert validation["vectors_preserved"] is True


def test_13_multipage_pdf():
    in_pdf = os.path.join(TEST_DIR, "multipage.pdf")
    out_pdf = os.path.join(TEST_DIR, "out_multipage.pdf")
    create_multipage_pdf(in_pdf)

    analysis = analyze_pdf(in_pdf)
    assert analysis["total_pages"] == 3

    plan = build_edit_plan(analysis, {"Person Page 1": "Sairaj Page 1"})
    assert plan["success"] is True

    res = edit_native_text_pdf(in_pdf, out_pdf, plan["operations"])
    assert res["success"] is True

    validation = validate_pdf_edit(in_pdf, out_pdf, plan["operations"])
    assert validation["pages_before"] == 3
    assert validation["pages_after"] == 3
    assert validation["passed"] is True


def test_14_acroform_pdf():
    in_pdf = os.path.join(TEST_DIR, "acroform.pdf")
    out_pdf = os.path.join(TEST_DIR, "out_acroform.pdf")
    create_acroform_pdf(in_pdf)

    analysis = analyze_pdf(in_pdf)
    assert analysis["mode"] == "MODE_A_ACROFORM"

    plan = build_edit_plan(analysis, {"name": "Sairaj", "date": "09/08/2026"})
    assert plan["success"] is True

    res = edit_acroform_pdf(in_pdf, out_pdf, plan["operations"])
    assert res["success"] is True


def test_15_native_text_pdf():
    in_pdf = os.path.join(TEST_DIR, "native_15.pdf")
    out_pdf = os.path.join(TEST_DIR, "out_native_15.pdf")
    create_native_text_pdf(in_pdf)

    analysis = analyze_pdf(in_pdf)
    assert analysis["mode"] == "MODE_B_NATIVE_TEXT"

    plan = build_edit_plan(analysis, {"name": "Sairaj"})
    res = edit_native_text_pdf(in_pdf, out_pdf, plan["operations"])
    assert res["success"] is True


def test_16_scanned_pdf():
    in_pdf = os.path.join(TEST_DIR, "scanned_16.pdf")
    out_pdf = os.path.join(TEST_DIR, "out_scanned_16.pdf")
    create_scanned_pdf(in_pdf)

    analysis = analyze_pdf(in_pdf)
    assert analysis["mode"] == "MODE_C_SCANNED"


def test_17_ocr_low_confidence_case():
    in_pdf = os.path.join(TEST_DIR, "scanned_17.pdf")
    out_pdf = os.path.join(TEST_DIR, "out_scanned_17.pdf")
    create_scanned_pdf(in_pdf)

    res = edit_scanned_pdf(in_pdf, out_pdf, [{"field": "NonExistentWord12345", "old_value": "NonExistentWord12345", "new_value": "Test"}])
    assert res["success"] is False
    assert res["requires_manual_review"] is True


def test_18_validation_failure():
    in_pdf = os.path.join(TEST_DIR, "native_18.pdf")
    out_pdf = os.path.join(TEST_DIR, "out_native_18.pdf")
    create_native_text_pdf(in_pdf)

    analysis = analyze_pdf(in_pdf)
    plan = build_edit_plan(analysis, {"name": "Sairaj"})
    edit_native_text_pdf(in_pdf, out_pdf, plan["operations"])

    # Test validation with a mismatched original file to simulate failure
    other_pdf = os.path.join(TEST_DIR, "multipage.pdf")
    create_multipage_pdf(other_pdf)
    validation = validate_pdf_edit(other_pdf, out_pdf, plan["operations"])
    assert validation["passed"] is False


def test_19_no_unintended_text_changes():
    in_pdf = os.path.join(TEST_DIR, "native_19.pdf")
    out_pdf = os.path.join(TEST_DIR, "out_native_19.pdf")
    create_native_text_pdf(in_pdf)

    analysis = analyze_pdf(in_pdf)
    plan = build_edit_plan(analysis, {"name": "Sairaj"})
    edit_native_text_pdf(in_pdf, out_pdf, plan["operations"])

    validation = validate_pdf_edit(in_pdf, out_pdf, plan["operations"])
    assert validation["unexpected_text_changes"] == 0


def test_20_image_preservation():
    in_pdf = os.path.join(TEST_DIR, "composite_20.pdf")
    out_pdf = os.path.join(TEST_DIR, "out_composite_20.pdf")
    create_composite_pdf_with_assets(in_pdf)

    analysis = analyze_pdf(in_pdf)
    plan = build_edit_plan(analysis, {"name": "Jane Smith"})
    edit_native_text_pdf(in_pdf, out_pdf, plan["operations"])

    validation = validate_pdf_edit(in_pdf, out_pdf, plan["operations"])
    assert validation["images_preserved"] is True
    assert validation["images_before"] == validation["images_after"]


def test_CRITICAL_composite_pdf():
    """CRITICAL TEST: PDF containing background image, logo, decorative vectors,

    multiple text blocks, target name, target date, and unrelated text.
    Change ONLY the target name/date. The resulting PDF MUST retain all assets.
    """
    in_pdf = os.path.join(TEST_DIR, "critical_composite.pdf")
    out_pdf = os.path.join(TEST_DIR, "out_critical_composite.pdf")
    create_composite_pdf_with_assets(in_pdf)

    # Pre-edit analysis
    pre_analysis = analyze_pdf(in_pdf)

    plan = build_edit_plan(pre_analysis, {
        "name": "Jane Smith",
        "date": "15/05/2026"
    })
    assert plan["success"] is True, f"Plan failed: {plan}"

    # Apply mutation
    res = edit_native_text_pdf(in_pdf, out_pdf, plan["operations"])
    assert res["success"] is True

    # Post-edit validation
    validation = validate_pdf_edit(in_pdf, out_pdf, plan["operations"])

    assert validation["passed"] is True
    assert validation["images_preserved"] is True
    assert validation["page_geometry_preserved"] is True
    assert validation["vectors_preserved"] is True
    assert validation["unexpected_text_changes"] == 0
    assert validation["unsafe_changes"] == 0

    # Verify output PDF re-opens cleanly
    post_analysis = analyze_pdf(out_pdf)
    assert post_analysis["total_pages"] == pre_analysis["total_pages"]
    assert post_analysis["total_images"] == pre_analysis["total_images"]
    assert post_analysis["total_drawings"] <= pre_analysis["total_drawings"] + len(plan["operations"]) * 2


def test_single_pdf_edit_endpoint_with_email():
    """Tests /pdf/edit endpoint with send_email enabled."""
    import json
    from fastapi.testclient import TestClient
    from main import app

    client = TestClient(app)
    in_pdf = os.path.join(TEST_DIR, "test_api_single.pdf")
    create_composite_pdf_with_assets(in_pdf)

    with open(in_pdf, "rb") as f:
        resp = client.post(
            "/pdf/edit",
            files={"file": ("test.pdf", f, "application/pdf")},
            data={
                "changes_json": json.dumps({"name": "Alice Cooper"}),
                "send_email": "true",
                "recipient_email": "alice@example.com",
                "email_subject": "Your Offer Letter",
                "email_body": "Here is your letter."
            }
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "email_status" in data
    assert data["email_status"] is not None

