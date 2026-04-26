"""
Cyrus — Red Ink / Colour Separator

PROBLEM: The exam papers photographed already have teacher annotations in red:
- Red tick marks ✓ on correct answers (Part A)
- Red score circled (e.g., "22/30")
- Red underlines and comments
- Red correction notes

If we OCR everything, we read the teacher's marks as part of the student's text.
The grading AI would then compare "✓ 22/30" against the answer key — wrong.

SOLUTION: Separate the image by ink colour before OCR.
- Student text = black ink → OCR this
- Teacher marks = red ink → isolate separately (store for context, don't grade)

HOW: Convert image to HSV colour space, use colour masking to
isolate red pixels (teacher marks) from dark/black pixels (student writing).
"""

import io
import numpy as np
from PIL import Image


def separate_red_ink(image_bytes: bytes) -> tuple[bytes, bytes]:
    """
    Separates student text (black) from teacher annotations (red).

    Args:
        image_bytes: Cleaned image bytes (after preprocessing)

    Returns:
        Tuple of:
        - student_image_bytes: Image with only black student writing (for OCR)
        - teacher_marks_bytes: Image with only red teacher annotations (for context)
    """
    import cv2

    # Load image
    img = np.array(Image.open(io.BytesIO(image_bytes)).convert("RGB"))
    img_bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

    # Convert to HSV (Hue-Saturation-Value) — better for colour detection than RGB
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)

    # ── Red ink mask ──────────────────────────────────────────
    # Red in HSV wraps around 0/180 degrees, so we need two ranges
    red_lower_1 = np.array([0, 70, 70])      # Hue 0–10: red
    red_upper_1 = np.array([10, 255, 255])
    red_lower_2 = np.array([160, 70, 70])    # Hue 160–180: also red
    red_upper_2 = np.array([180, 255, 255])

    mask_red_1 = cv2.inRange(hsv, red_lower_1, red_upper_1)
    mask_red_2 = cv2.inRange(hsv, red_lower_2, red_upper_2)
    red_mask = cv2.bitwise_or(mask_red_1, mask_red_2)

    # Dilate slightly to capture full red strokes (not just center pixels)
    kernel = np.ones((3, 3), np.uint8)
    red_mask = cv2.dilate(red_mask, kernel, iterations=1)

    # ── Student image: replace red regions with white ────────
    student_img = img_bgr.copy()
    student_img[red_mask > 0] = [255, 255, 255]  # white out red areas

    # Convert student image to grayscale binary (black text on white)
    student_gray = cv2.cvtColor(student_img, cv2.COLOR_BGR2GRAY)
    _, student_binary = cv2.threshold(student_gray, 180, 255, cv2.THRESH_BINARY)

    # ── Teacher marks image: extract only red regions ────────
    teacher_img = np.ones_like(img_bgr) * 255  # white background
    teacher_img[red_mask > 0] = img_bgr[red_mask > 0]

    # Encode both as JPEG
    def to_bytes(cv_img: np.ndarray) -> bytes:
        _, buf = cv2.imencode(".jpg", cv_img, [cv2.IMWRITE_JPEG_QUALITY, 93])
        return bytes(buf)

    return to_bytes(student_binary), to_bytes(teacher_img)


def estimate_red_ink_coverage(image_bytes: bytes) -> float:
    """
    Returns the percentage of the image covered by red ink (0.0 to 1.0).
    Useful for detecting whether a paper is already graded.
    Papers with >5% red coverage likely have existing teacher marks.
    """
    import cv2

    img = np.array(Image.open(io.BytesIO(image_bytes)).convert("RGB"))
    img_bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)

    mask_1 = cv2.inRange(hsv, np.array([0, 70, 70]), np.array([10, 255, 255]))
    mask_2 = cv2.inRange(hsv, np.array([160, 70, 70]), np.array([180, 255, 255]))
    red_mask = cv2.bitwise_or(mask_1, mask_2)

    total_pixels = red_mask.shape[0] * red_mask.shape[1]
    red_pixels = int(np.sum(red_mask > 0))
    return red_pixels / total_pixels if total_pixels > 0 else 0.0
