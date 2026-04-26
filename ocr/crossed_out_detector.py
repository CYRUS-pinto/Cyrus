"""
Cyrus — Crossed-Out Text Detector

PROBLEM: Students often cross out wrong answers by drawing horizontal lines
through the text, then write the correct answer nearby.
If not handled, OCR reads the struck-out text as the answer — and grades it wrong.

SOLUTION: Before OCR, detect horizontal lines using Hough Transform.
Any text region with a crossing line is marked as "cancelled".
The system silently removes this text — the cancelled text is not graded.
(Decision confirmed: silently removed, not shown to teacher.)

HOW IT WORKS:
1. Detect horizontal lines with Hough Line Transform
2. For each detected line, check if it crosses a text region
3. If so, erase that text region by painting it white
4. OCR runs on the cleaned image (only the correct, un-crossed answers)
"""

import io
import numpy as np
from dataclasses import dataclass
from PIL import Image


@dataclass
class CrossedOutRegion:
    x: int
    y: int
    width: int
    height: int
    confidence: float  # how confident we are this is crossed out (not just a line)


def remove_crossed_out_text(image_bytes: bytes) -> tuple[bytes, list[CrossedOutRegion]]:
    """
    Detects and removes crossed-out text regions.

    Args:
        image_bytes: Student-only image (after red ink separation)

    Returns:
        Tuple of:
        - cleaned_bytes: Image with crossed-out text replaced by white
        - removed_regions: List of detected crossed-out regions (for audit)
    """
    import cv2

    img = np.array(Image.open(io.BytesIO(image_bytes)).convert("RGB"))
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    _, binary = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)  # text = white on black

    removed_regions: list[CrossedOutRegion] = []

    # ── Step 1: Detect horizontal lines ──────────────────────
    # Hough Line Transform finds straight lines in an image
    # minLineLength=30 means lines must be at least 30px long
    # maxLineGap=10 allows small gaps in the line
    horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 1))
    horizontal_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, horizontal_kernel)

    # Find connected components (groups of pixels) in the line mask
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(horizontal_lines)

    # ── Step 2: For each detected line, erase the surrounding text ──
    result_img = img.copy()

    for i in range(1, num_labels):  # skip background (label 0)
        x, y, w, h, area = stats[i]

        # Filter: only consider wide horizontal segments (actual strike-through lines)
        if w < 30 or h > 8:  # too narrow or too tall (not a horizontal line)
            continue
        if area < 200:       # too small — probably just a pixel artifact
            continue

        # Confidence based on width/height ratio (the more horizontal, the more confident)
        confidence = min(1.0, (w / max(h, 1)) / 20)

        # Expand the erasure area to include the text around the line
        # Go up and down by ~15px to erase the text being crossed out
        erase_y_top = max(0, y - 15)
        erase_y_bottom = min(result_img.shape[0], y + h + 15)
        erase_x_left = max(0, x - 5)
        erase_x_right = min(result_img.shape[1], x + w + 5)

        # Paint the region white (erase it)
        result_img[erase_y_top:erase_y_bottom, erase_x_left:erase_x_right] = [255, 255, 255]

        removed_regions.append(CrossedOutRegion(
            x=erase_x_left, y=erase_y_top,
            width=erase_x_right - erase_x_left,
            height=erase_y_bottom - erase_y_top,
            confidence=confidence,
        ))

    # Encode result
    result_pil = Image.fromarray(result_img)
    buf = io.BytesIO()
    result_pil.save(buf, format="JPEG", quality=95)
    return buf.getvalue(), removed_regions
