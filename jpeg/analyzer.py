"""JPEG Image Analyzer Module.

Uses PyTesseract and OpenCV/Pillow to detect text boxes, font properties (size, color, background),
and potential free-space regions in uploaded JPEG images.
"""

from typing import Dict, Any, List, Tuple
import os

_OCR_DEPS_AVAILABLE: bool | None = None


def check_ocr_deps() -> bool:
    """Returns True if Pillow, NumPy, OpenCV, and PyTesseract are available."""
    global _OCR_DEPS_AVAILABLE
    if _OCR_DEPS_AVAILABLE is not None:
        return _OCR_DEPS_AVAILABLE
    try:
        from PIL import Image  # noqa: F401
        import numpy  # noqa: F401
        import cv2  # noqa: F401
        import pytesseract  # noqa: F401
        _OCR_DEPS_AVAILABLE = True
    except ImportError:
        _OCR_DEPS_AVAILABLE = False
    return _OCR_DEPS_AVAILABLE


def analyze_jpeg(image_path: str) -> Dict[str, Any]:
    """Analyzes a JPEG image and returns dimensions, detected text bounding boxes,

    estimated font properties (size/color), and candidate free-space placement regions.
    """
    from PIL import Image

    if not os.path.exists(image_path):
        return {"success": False, "error": f"Image file not found: {image_path}"}

    try:
        with Image.open(image_path) as img:
            width, height = img.size
            img_mode = img.mode
    except Exception as e:
        return {"success": False, "error": f"Failed to open image: {str(e)}"}

    result: Dict[str, Any] = {
        "success": True,
        "width": width,
        "height": height,
        "mode": img_mode,
        "ocr_available": False,
        "detected_fields": []
    }

    if not check_ocr_deps():
        return result

    import cv2
    import numpy as np
    import pytesseract

    try:
        img_np = cv2.imread(image_path)
        if img_np is None:
            return result

        ocr_data = pytesseract.image_to_data(img_np, output_type=pytesseract.Output.DICT)
        result["ocr_available"] = True

        n_boxes = len(ocr_data["text"])
        detected_fields = []

        # Group words into blocks/lines if possible
        for i in range(n_boxes):
            word = (ocr_data["text"][i] or "").strip()
            conf = float(ocr_data["conf"][i]) if ocr_data["conf"][i] != "-1" else 0.0

            if word and conf >= 40.0:
                x = int(ocr_data["left"][i])
                y = int(ocr_data["top"][i])
                w = int(ocr_data["width"][i])
                h = int(ocr_data["height"][i])

                # Sample local background color (perimeter pixels outside bounding box)
                bg_color = _sample_bg_color(img_np, x, y, w, h)
                fg_color = _sample_fg_color(img_np, x, y, w, h, bg_color)

                detected_fields.append({
                    "text": word,
                    "box": [x, y, w, h],
                    "confidence": round(conf, 1),
                    "estimated_font_size": max(10, int(h * 0.85)),
                    "bg_color_rgb": bg_color,
                    "fg_color_rgb": fg_color
                })

        # Compute document-wide median font size and dominant text color for consistent styling
        font_sizes = [f["estimated_font_size"] for f in detected_fields if f["estimated_font_size"] > 0]
        doc_median_font_size = int(np.median(font_sizes)) if font_sizes else 22

        fg_colors = [f["fg_color_rgb"] for f in detected_fields]
        if fg_colors:
            doc_dominant_fg_color = tuple(int(c) for c in np.median(fg_colors, axis=0))
        else:
            doc_dominant_fg_color = (0, 0, 0)

        result["detected_fields"] = detected_fields
        result["doc_median_font_size"] = doc_median_font_size
        result["doc_dominant_fg_color"] = doc_dominant_fg_color

    except Exception as e:
        result["ocr_error"] = str(e)

    return result



def find_nearest_text_properties(
    detected_fields: List[Dict[str, Any]],
    target_x: int,
    target_y: int,
    default_size: int = 24,
    default_color: Tuple[int, int, int] = (0, 0, 0)
) -> Tuple[int, Tuple[int, int, int]]:
    """Finds the nearest detected text box to (target_x, target_y) and extracts its font size and RGB color."""
    if not detected_fields:
        return default_size, default_color

    best_dist = float("inf")
    best_size = default_size
    best_color = default_color

    for field in detected_fields:
        box = field.get("box", [0, 0, 0, 0])
        cx = box[0] + box[2] // 2
        cy = box[1] + box[3] // 2
        dist = (cx - target_x) ** 2 + (cy - target_y) ** 2

        if dist < best_dist:
            best_dist = dist
            best_size = field.get("estimated_font_size", default_size)
            best_color = tuple(field.get("fg_color_rgb", default_color))

    return best_size, best_color


def _sample_bg_color(img_np: Any, x: int, y: int, w: int, h: int) -> Tuple[int, int, int]:
    """Samples background color surrounding bounding box."""
    H, W, _ = img_np.shape
    pad = 4
    x1, y1 = max(0, x - pad), max(0, y - pad)
    x2, y2 = min(W, x + w + pad), min(H, y + h + pad)

    roi = img_np[y1:y2, x1:x2]
    if roi.size == 0:
        return (255, 255, 255)

    # Median color of outer border
    border_pixels = []
    border_pixels.extend(roi[0, :].tolist())
    border_pixels.extend(roi[-1, :].tolist())
    border_pixels.extend(roi[:, 0].tolist())
    border_pixels.extend(roi[:, -1].tolist())

    if not border_pixels:
        return (255, 255, 255)

    import numpy as np
    med_bgr = np.median(border_pixels, axis=0)
    # Return RGB
    return (int(med_bgr[2]), int(med_bgr[1]), int(med_bgr[0]))


def _sample_fg_color(img_np: Any, x: int, y: int, w: int, h: int, bg_rgb: Tuple[int, int, int]) -> Tuple[int, int, int]:
    """Samples foreground text color inside bounding box by selecting pixels with highest contrast to bg_rgb."""
    H, W, _ = img_np.shape
    x1, y1 = max(0, x), max(0, y)
    x2, y2 = min(W, x + w), min(H, y + h)

    roi = img_np[y1:y2, x1:x2]
    if roi.size == 0:
        return (0, 0, 0)

    import numpy as np
    roi_rgb = roi[:, :, ::-1]  # Convert BGR to RGB
    diff = np.abs(roi_rgb.astype(int) - np.array(bg_rgb))
    dist = np.sum(diff, axis=2)

    # Pick top 20% most contrasting pixels
    threshold = np.percentile(dist, 80)
    fg_pixels = roi_rgb[dist >= threshold]

    if fg_pixels.size == 0:
        return (0, 0, 0)

    med_fg = np.median(fg_pixels, axis=0)
    return (int(med_fg[0]), int(med_fg[1]), int(med_fg[2]))
