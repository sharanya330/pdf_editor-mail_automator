"""Unit & API Integration Tests for JPEG Editor Module."""

import os
import sys
import json
import pytest
from PIL import Image, ImageDraw

# Ensure workspace root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jpeg.analyzer import analyze_jpeg
from jpeg.editor import edit_jpeg
from jpeg.bulk_processor import process_bulk_jpeg_edits
from fastapi.testclient import TestClient
from main import app

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
SAMPLE_JPEG_PATH = os.path.join(TEST_DIR, "sample_test_template.jpg")


@pytest.fixture(scope="module", autouse=True)
def create_sample_jpeg():
    """Generates a synthetic sample JPEG image for testing."""
    img = Image.new("RGB", (600, 400), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    # Add title and fields
    draw.text((50, 40), "OFFER LETTER", fill=(0, 0, 0))
    draw.text((50, 100), "Candidate Name: John Doe", fill=(0, 0, 0))
    draw.text((50, 160), "Designation: Software Engineer", fill=(0, 0, 0))
    draw.text((50, 220), "Date of Issue:", fill=(0, 0, 0))  # Free space after label
    img.save(SAMPLE_JPEG_PATH, "JPEG", quality=95)
    yield
    if os.path.exists(SAMPLE_JPEG_PATH):
        try:
            os.remove(SAMPLE_JPEG_PATH)
        except Exception:
            pass


def test_analyze_jpeg():
    """Tests image dimension and OCR analysis on synthetic JPEG."""
    res = analyze_jpeg(SAMPLE_JPEG_PATH)
    assert res["success"] is True
    assert res["width"] == 600
    assert res["height"] == 400


def test_single_jpeg_edit():
    """Tests single JPEG text replacement and free-space insertion."""
    out_path = os.path.join(TEST_DIR, "test_single_out.jpg")
    try:
        res = edit_jpeg(
            input_image_path=SAMPLE_JPEG_PATH,
            output_image_path=out_path,
            replacements=[
                {"target": "John Doe", "new_value": "Alice Smith", "box": [170, 95, 120, 25]}
            ],
            insertions=[
                {"x": 200, "y": 220, "text": "2026-09-09", "font_size": 18, "font_color": "#000000"}
            ]
        )
        assert res["success"] is True
        assert os.path.exists(out_path)

        # Verify edited image can be opened
        with Image.open(out_path) as edited_img:
            assert edited_img.size == (600, 400)
    finally:
        if os.path.exists(out_path):
            os.remove(out_path)


def test_jpeg_api_endpoints():
    """Tests FastAPI /jpeg/analyze and /jpeg/edit endpoints."""
    client = TestClient(app)

    with open(SAMPLE_JPEG_PATH, "rb") as f:
        resp_analyze = client.post(
            "/jpeg/analyze",
            files={"file": ("sample.jpg", f, "image/jpeg")}
        )
    assert resp_analyze.status_code == 200
    analyze_data = resp_analyze.json()
    assert analyze_data["success"] is True
    assert analyze_data["width"] == 600

    with open(SAMPLE_JPEG_PATH, "rb") as f:
        resp_edit = client.post(
            "/jpeg/edit",
            files={"file": ("sample.jpg", f, "image/jpeg")},
            data={
                "replacements_json": json.dumps([{"target": "Software Engineer", "new_value": "Senior AI Developer", "box": [160, 155, 180, 25]}]),
                "insertions_json": json.dumps([{"x": 200, "y": 220, "text": "CONFIRMED", "font_size": 20}]),
                "send_email": "false"
            }
        )
    assert resp_edit.status_code == 200
    edit_data = resp_edit.json()
    assert edit_data["success"] is True
    assert "download_url" in edit_data
    assert edit_data["download_url"].startswith("/jpeg/download/")


def test_bulk_jpeg_processor(tmp_path):
    """Tests bulk JPEG data processing using a synthetic CSV file."""
    csv_path = tmp_path / "candidates.csv"
    csv_content = "Full_Name,Role,Joining_Date\nBob Miller,Data Scientist,2026-10-01\nCarol White,Product Manager,2026-10-15\n"
    csv_path.write_text(csv_content, encoding="utf-8")

    out_dir = tmp_path / "bulk_out"

    mappings = [
        {"field": "John Doe", "excel_column": "Full_Name", "is_free_space": False, "box": [170, 95, 120, 25]},
        {"x": 200, "y": 220, "excel_column": "Joining_Date", "is_free_space": True, "font_size": 16}
    ]

    res = process_bulk_jpeg_edits(
        jpeg_template_path=SAMPLE_JPEG_PATH,
        data_file_path=str(csv_path),
        output_dir=str(out_dir),
        mapping_config=mappings
    )

    assert res["success"] is True
    assert res["total_rows"] == 2
    assert res["generated_count"] == 2
    assert "zip_file" in res
    assert os.path.exists(os.path.join(str(out_dir), res["zip_file"]))


def test_bulk_jpeg_email_preflight_missing_column(tmp_path):
    """Tests pre-flight validation error when email is enabled without recipient email column."""
    csv_path = tmp_path / "candidates.csv"
    csv_path.write_text("Name,Email\nTest Candidate,test@example.com\n", encoding="utf-8")
    out_dir = tmp_path / "bulk_out_email"

    res = process_bulk_jpeg_edits(
        jpeg_template_path=SAMPLE_JPEG_PATH,
        data_file_path=str(csv_path),
        output_dir=str(out_dir),
        mapping_config=[],
        send_email_toggle=True,
        email_column_name=None
    )
    assert res["success"] is False
    assert "no recipient email column" in res["message"]

