"""JPEG Image Text & Free-Space Editor Engine.

Edits target text in JPEG images by erasing detected text regions with sampled background colors,
and drawing replacement text. Also supports free-space text insertions using explicit coordinates
or anchor labels with auto-detected/custom font properties.
"""

from typing import Dict, Any, List, Optional, Tuple
import os
import re
from PIL import Image, ImageDraw, ImageFont
from jpeg.analyzer import analyze_jpeg, find_nearest_text_properties, _sample_bg_color, check_ocr_deps


def edit_jpeg(
    input_image_path: str,
    output_image_path: str,
    replacements: Optional[List[Dict[str, Any]]] = None,
    insertions: Optional[List[Dict[str, Any]]] = None,
    quality: int = 95
) -> Dict[str, Any]:
    """Edits a JPEG image by replacing specified target text regions and inserting free-space values.

    Args:
        input_image_path: Path to source JPEG file.
        output_image_path: Destination path for edited JPEG file.
        replacements: List of dicts, e.g. [{"target": "John Doe", "new_value": "Alice Cooper", "box": [x,y,w,h]}]
        insertions: List of dicts, e.g. [{"x": 120, "y": 450, "text": "APPROVED", "font_size": 20, "font_color": "#000000"}]
        quality: JPEG output quality (1-100).
    """
    if not os.path.exists(input_image_path):
        return {"success": False, "error": f"Input image does not exist: {input_image_path}"}

    replacements = replacements or []
    insertions = insertions or []

    try:
        image = Image.open(input_image_path).convert("RGB")
    except Exception as e:
        return {"success": False, "error": f"Failed to load image: {str(e)}"}

    img_w, img_h = image.size
    draw = ImageDraw.Draw(image)

    # Perform analysis if OCR is available for auto-detection
    analysis_res = analyze_jpeg(input_image_path)
    detected_fields = analysis_res.get("detected_fields", []) if analysis_res.get("success") else []
    doc_median_size = analysis_res.get("doc_median_font_size", 22)
    doc_dominant_color = analysis_res.get("doc_dominant_fg_color", (0, 0, 0))

    # 1. Process Text Replacements
    applied_replacements = 0
    if check_ocr_deps():
        import cv2
        img_np = cv2.imread(input_image_path)
    else:
        img_np = None

    for rep in replacements:
        target_text = (rep.get("target") or rep.get("old_value") or rep.get("field") or "").strip()
        new_text = str(rep.get("new_value") or rep.get("value") or "")
        custom_box = rep.get("box")

        matched_boxes = []
        if custom_box and len(custom_box) == 4:
            matched_boxes.append(custom_box)
        elif target_text and detected_fields:
            # Match target_text against detected OCR fields
            target_lower = target_text.lower()
            matching_field_boxes = []

            for field in detected_fields:
                field_text = field["text"].lower()
                if field_text == target_lower or target_lower in field_text or field_text in target_lower:
                    matching_field_boxes.append(field["box"])

            if matching_field_boxes:
                # Merge adjacent/line-aligned bounding boxes into single target bounds
                min_x = min(b[0] for b in matching_field_boxes)
                min_y = min(b[1] for b in matching_field_boxes)
                max_x = max(b[0] + b[2] for b in matching_field_boxes)
                max_y = max(b[1] + b[3] for b in matching_field_boxes)

                merged_w = max_x - min_x
                merged_h = max_y - min_y
                matched_boxes.append([min_x, min_y, merged_w, merged_h])


        for box in matched_boxes:
            x, y, w, h = box[0], box[1], box[2], box[3]
            
            # Determine background color to paint over
            if img_np is not None:
                bg_color = _sample_bg_color(img_np, x, y, w, h)
            else:
                bg_color = (255, 255, 255)

            # Patch/erase original text area with local background color
            draw.rectangle([x, y, x + w, y + h], fill=bg_color)

            # Determine font size and text color
            est_size, est_color = find_nearest_text_properties(detected_fields, x, y, default_size=doc_median_size, default_color=doc_dominant_color)
            initial_size = int(rep.get("font_size") or est_size or doc_median_size)
            font_color = _parse_color(rep.get("font_color"), est_color)

            # Fit font size to target box width and height so it fits seamlessly
            font, font_size, text_w, text_h = _fit_font_to_bounds(draw, new_text, initial_size, max_w=max(w, 80), max_h=max(h, 20))

            # Vertical centering alignment inside target box height
            aligned_y = max(0, y + (h - text_h) // 2)

            draw.text((x, aligned_y), new_text, fill=font_color, font=font)
            applied_replacements += 1

    # 2. Process Free-Space Text Insertions
    applied_insertions = 0
    for ins in insertions:
        text_to_insert = str(ins.get("text") or ins.get("value") or "")
        if not text_to_insert:
            continue

        target_x = ins.get("x")
        target_y = ins.get("y")
        anchor_label = (ins.get("anchor") or "").strip()

        # If anchor label is specified, find its coordinate and align next to it
        if anchor_label and detected_fields:
            anchor_lower = anchor_label.lower()
            for field in detected_fields:
                if anchor_lower in field["text"].lower():
                    abox = field["box"]
                    # Position immediately right of anchor with padding
                    target_x = abox[0] + abox[2] + 12
                    target_y = abox[1]
                    break

        if target_x is None or target_y is None:
            target_x, target_y = 50, 50

        target_x = int(target_x)
        target_y = int(target_y)

        # Auto-detect font size and color from nearest text region or document stats
        auto_size, auto_color = find_nearest_text_properties(detected_fields, target_x, target_y, default_size=doc_median_size, default_color=doc_dominant_color)
        initial_size = int(ins.get("font_size") or auto_size or doc_median_size)
        font_color = _parse_color(ins.get("font_color"), auto_color)

        # Available space right to edge of image
        avail_w = max(50, img_w - target_x - 10)
        avail_h = max(20, int(initial_size * 1.5))

        font, font_size, text_w, text_h = _fit_font_to_bounds(draw, text_to_insert, initial_size, max_w=avail_w, max_h=avail_h)

        draw.text((target_x, target_y), text_to_insert, fill=font_color, font=font)
        applied_insertions += 1

    # Save output JPEG image with high quality
    out_dir = os.path.dirname(output_image_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    image.save(output_image_path, "JPEG", quality=quality)

    return {
        "success": True,
        "output_path": output_image_path,
        "applied_replacements": applied_replacements,
        "applied_insertions": applied_insertions
    }


def _fit_font_to_bounds(
    draw: ImageDraw.ImageDraw,
    text: str,
    initial_size: int,
    max_w: int,
    max_h: int
) -> Tuple[ImageFont.ImageFont | ImageFont.FreeTypeFont, int, int, int]:
    """Dynamically scales down font size until text fits within max_w and max_h bounds."""
    size = max(8, initial_size)

    for sz in range(size, 7, -1):
        font = _get_font(sz)
        try:
            bbox = draw.textbbox((0, 0), text, font=font)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
        except Exception:
            tw = int(draw.textlength(text, font=font))
            th = int(sz * 1.2)

        if tw <= max_w and th <= max_h + 10:
            return font, sz, tw, th

    font = _get_font(8)
    return font, 8, max_w, max_h


def _get_font(font_size: int) -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
    """Gets Open Sans Italic ImageFont instance exclusively for all JPEG edits."""
    font_size = max(8, font_size)
    
    # 1. Bundled Open Sans Italic font
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    bundled_font_path = os.path.join(project_root, "fonts", "OpenSans-Italic.ttf")

    if os.path.exists(bundled_font_path):
        try:
            return ImageFont.truetype(bundled_font_path, font_size)
        except Exception:
            pass

    # 2. System fallbacks if font is moved
    ttf_paths = [
        "OpenSans-Italic.ttf",
        "fonts/OpenSans-Italic.ttf",
        "/System/Library/Fonts/Supplemental/Arial Italic.ttf"
    ]
    for font_path in ttf_paths:
        if os.path.exists(font_path):
            try:
                return ImageFont.truetype(font_path, font_size)
            except Exception:
                pass
    try:
        return ImageFont.load_default(size=font_size)
    except Exception:
        return ImageFont.load_default()



def _parse_color(color_val: Any, default_rgb: Tuple[int, int, int]) -> Tuple[int, int, int]:
    """Parses color representation (hex string, list/tuple RGB, or color name) into an (R,G,B) tuple."""
    if not color_val:
        return default_rgb

    if isinstance(color_val, (list, tuple)) and len(color_val) >= 3:
        return (int(color_val[0]), int(color_val[1]), int(color_val[2]))

    if isinstance(color_val, str):
        color_str = color_val.strip()
        if color_str.startswith("#"):
            hex_val = color_str.lstrip("#")
            if len(hex_val) == 6:
                return (int(hex_val[0:2], 16), int(hex_val[2:4], 16), int(hex_val[4:6], 16))
            elif len(hex_val) == 3:
                return (int(hex_val[0]*2, 16), int(hex_val[1]*2, 16), int(hex_val[2]*2, 16))

    return default_rgb
