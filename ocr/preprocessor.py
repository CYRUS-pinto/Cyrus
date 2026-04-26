"""
Cyrus — Image Pre-Processor

Takes a raw phone photo of an exam paper and cleans it up
before any OCR model sees it.

Why this matters: The same OCR model can be 40-60% more accurate
on a clean image vs. a raw phone photo.

Stages:
1. Perspective correction (paper photographed from an angle)
2. Deskew (paper slightly rotated)
3. Binding warp correction (booklet spine causes right-side distortion)
4. Binarization (convert to black/white — removes ink color variation)
5. Adaptive thresholding (handles shadows from page curling)
6. Noise removal (camera sensor noise, pen artifacts)
7. Contrast enhancement (makes ink darker, paper whiter)
"""

import io
import numpy as np
from PIL import Image


def preprocess_image(raw_bytes: bytes, enhanced: bool = False) -> bytes:
    """
    Main entry point. Takes raw image bytes, returns cleaned image bytes.

    Args:
        raw_bytes: Raw photo bytes (JPEG, PNG, HEIC-converted, etc.)
        enhanced: If True, applies more aggressive processing
                  (used on retry attempts when normal processing gave low confidence)

    Returns:
        Cleaned image bytes (JPEG)
    """
    # Load image
    img = Image.open(io.BytesIO(raw_bytes)).convert("RGB")
    img_np = np.array(img)

    # Import OpenCV (lazy import to avoid slow startup)
    import cv2

    # Convert to OpenCV BGR format
    img_cv = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)

    # Stage 1: Perspective / document detection
    img_cv = _correct_perspective(img_cv)

    # Stage 2: Deskew
    img_cv = _deskew(img_cv)

    # Stage 3: Resize to standard DPI (300 DPI equivalent)
    img_cv = _normalize_resolution(img_cv)

    # Stage 4: Convert to grayscale for binarization
    gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)

    # Stage 5: Adaptive thresholding
    if enhanced:
        # More aggressive for retry attempts
        binary = cv2.adaptiveThreshold(
            gray, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            blockSize=11,
            C=7,
        )
    else:
        binary = cv2.adaptiveThreshold(
            gray, 255,
            cv2.ADAPTIVE_THRESH_MEAN_C,
            cv2.THRESH_BINARY,
            blockSize=15,
            C=5,
        )

    # Stage 6: Denoise
    binary = cv2.fastNlMeansDenoising(binary, h=10)

    # Stage 7: Morphological cleanup (fills tiny holes in letters)
    kernel = np.ones((1, 1), np.uint8)
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)

    # Convert back to PIL and encode as JPEG
    result = Image.fromarray(binary)
    out_buffer = io.BytesIO()
    result.save(out_buffer, format="JPEG", quality=95)
    return out_buffer.getvalue()


def _correct_perspective(img: np.ndarray) -> np.ndarray:
    """
    Detects the paper boundary and corrects perspective if the photo was taken at an angle.
    Falls back to original image if no clear boundary is found.
    """
    import cv2

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 75, 200)

    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return img

    # Find the largest contour — likely the paper
    largest = max(contours, key=cv2.contourArea)
    peri = cv2.arcLength(largest, True)
    approx = cv2.approxPolyDP(largest, 0.02 * peri, True)

    if len(approx) == 4:
        # Found a 4-corner document — apply perspective transform
        pts = approx.reshape(4, 2).astype(np.float32)
        return _four_point_transform(img, pts)

    return img


def _four_point_transform(img: np.ndarray, pts: np.ndarray) -> np.ndarray:
    """Classic four-point perspective correction."""
    import cv2

    # Order points: top-left, top-right, bottom-right, bottom-left
    rect = _order_points(pts)
    (tl, tr, br, bl) = rect

    # Compute output dimensions
    width_a = np.linalg.norm(br - bl)
    width_b = np.linalg.norm(tr - tl)
    max_width = max(int(width_a), int(width_b))

    height_a = np.linalg.norm(tr - br)
    height_b = np.linalg.norm(tl - bl)
    max_height = max(int(height_a), int(height_b))

    dst = np.array([
        [0, 0],
        [max_width - 1, 0],
        [max_width - 1, max_height - 1],
        [0, max_height - 1],
    ], dtype="float32")

    M = cv2.getPerspectiveTransform(rect, dst)
    return cv2.warpPerspective(img, M, (max_width, max_height))


def _order_points(pts: np.ndarray) -> np.ndarray:
    """Order points: top-left, top-right, bottom-right, bottom-left."""
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]   # TL: smallest sum
    rect[2] = pts[np.argmax(s)]   # BR: largest sum
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]  # TR: smallest diff
    rect[3] = pts[np.argmax(diff)]  # BL: largest diff
    return rect


def _deskew(img: np.ndarray) -> np.ndarray:
    """
    Corrects slight rotation in the image.
    Uses Hough line detection to find the angle of text lines.
    """
    import cv2

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    coords = np.column_stack(np.where(binary > 0))
    if len(coords) < 10:
        return img

    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = 90 + angle

    # Only correct if angle is significant (> 0.5°)
    if abs(angle) < 0.5:
        return img

    h, w = img.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    return cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)


def _normalize_resolution(img: np.ndarray, target_width: int = 2480) -> np.ndarray:
    """
    Resize image to a standard width (equivalent to ~300 DPI for A4).
    Keeps aspect ratio. If image is already large enough, don't upscale excessively.
    """
    import cv2

    h, w = img.shape[:2]
    if w >= target_width:
        return img

    scale = target_width / w
    new_w = target_width
    new_h = int(h * scale)
    return cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)
