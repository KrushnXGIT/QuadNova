"""
quality.py
==========
Image and ROI quality checks for the conjunctiva anaemia screening pipeline.

All checks return a QualityResult named tuple. Images that fail any check should
be rejected from the CV pipeline (they will not produce reliable model input).

Checks implemented
------------------
1. Invalid image        — cannot be loaded at all (corrupted, zero-byte, wrong format)
2. Low resolution       — min(H, W) below MIN_DIMENSION; image too small to extract
                          meaningful colour/texture features from the ROI
3. Excessive brightness — mean L-channel luminance above BRIGHT_THRESHOLD; indicates
                          blown-out / over-exposed images where tissue colour is lost
4. Excessive darkness   — mean L-channel luminance below DARK_THRESHOLD; near-black
                          images where the ROI is invisible
5. Blur                 — Laplacian variance below BLUR_THRESHOLD; indicates motion
                          blur or extreme de-focus that destroys texture features.
                          Laplacian variance is a standard, fast, reference-free
                          blur estimator (suitable for deployment without a
                          reference image)
6. Poor ROI coverage    — the ROI mask covers less than MIN_ROI_COVERAGE_FRACTION of
                          the image; likely a mis-captured or mis-aligned image

Threshold justification
-----------------------
Thresholds below are heuristic defaults, not clinically validated cut-offs.
They are intentionally named constants so they can be adjusted without code changes.
The correct values for any specific deployment context should be validated against
real images from that context. Do NOT present these thresholds as medically validated
quality criteria.

These checks are designed to be applied at two points in the pipeline:
  A. On the full raw image BEFORE ROI extraction.
  B. On the extracted ROI AFTER extraction (via check_roi_quality).
"""

import logging
from typing import NamedTuple, Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Thresholds (all heuristic — see module docstring)
# ---------------------------------------------------------------------------

# Minimum accepted dimension (pixels) in the shorter axis of the image.
# Below this, the image is likely too small to contain useful conjunctiva detail.
MIN_DIMENSION: int = 100

# Laplacian variance threshold below which an image is considered too blurry.
# Value calibrated for conjunctiva images resized to roughly 224×224;
# may need tuning at full raw resolution.
BLUR_THRESHOLD: float = 50.0

# L-channel (in CIE LAB, L in [0,100]) mean luminance thresholds.
# Values from OpenCV's LAB conversion where L is in [0, 255] range.
DARK_THRESHOLD: float = 20.0   # L < 20/255 → near-black image
BRIGHT_THRESHOLD: float = 230.0  # L > 230/255 → near-white / blown-out image

# Minimum fraction of image pixels that must be inside the ROI mask.
# Below this, the mask likely didn't align properly with the image.
MIN_ROI_COVERAGE_FRACTION: float = 0.01


class QualityResult(NamedTuple):
    """
    Result of a quality check.

    Attributes:
        passed:  True if the image meets all quality criteria.
        reason:  Human-readable explanation. 'OK' if passed.
        metrics: Dict of computed metric values (blur_score, mean_luminance, etc.)
                 for logging / downstream inspection.
        checks:  Dict[check_name, bool] — individual pass/fail for each check.
    """
    passed: bool
    reason: str
    metrics: dict
    checks: dict


def _compute_blur_score(gray: np.ndarray) -> float:
    """
    Return the Laplacian variance of a grayscale image as a blur score.
    Higher = sharper. Below BLUR_THRESHOLD = too blurry.
    """
    lap = cv2.Laplacian(gray, cv2.CV_64F)
    return float(lap.var())


def _compute_luminance_stats(rgb: np.ndarray) -> dict:
    """
    Convert RGB [0,255] uint8 to CIE LAB and return L-channel statistics.
    OpenCV LAB L is in [0, 255] when input is uint8.
    """
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB)
    l_channel = lab[:, :, 0].astype(np.float32)
    return {
        "mean_luminance": float(l_channel.mean()),
        "std_luminance": float(l_channel.std()),
        "min_luminance": float(l_channel.min()),
        "max_luminance": float(l_channel.max()),
    }


def check_image_quality(
    rgb: np.ndarray,
    blur_threshold: float = BLUR_THRESHOLD,
    dark_threshold: float = DARK_THRESHOLD,
    bright_threshold: float = BRIGHT_THRESHOLD,
    min_dimension: int = MIN_DIMENSION,
) -> QualityResult:
    """
    Run all quality checks on a raw image (before ROI extraction).

    Args:
        rgb:              (H, W, 3) uint8 RGB array (EXIF-corrected, not yet cropped).
        blur_threshold:   Laplacian variance threshold (default: BLUR_THRESHOLD).
        dark_threshold:   L-channel mean threshold for darkness (default: DARK_THRESHOLD).
        bright_threshold: L-channel mean threshold for brightness (default: BRIGHT_THRESHOLD).
        min_dimension:    Minimum acceptable shorter-axis dimension (default: MIN_DIMENSION).

    Returns:
        QualityResult. If passed=False, `reason` explains the first failing check.
    """
    if rgb is None or not isinstance(rgb, np.ndarray):
        return QualityResult(
            passed=False,
            reason="invalid_image: input is None or not an array",
            metrics={},
            checks={"valid_array": False},
        )

    if rgb.ndim != 3 or rgb.shape[2] != 3:
        return QualityResult(
            passed=False,
            reason=f"invalid_image: expected (H,W,3) array, got shape {rgb.shape}",
            metrics={},
            checks={"valid_array": False},
        )

    h, w = rgb.shape[:2]
    metrics = {
        "height": h,
        "width": w,
        "min_dimension": min(h, w),
    }
    checks = {}
    failure_reason = "OK"

    # --- Check 1: resolution ---
    checks["min_dimension"] = min(h, w) >= min_dimension
    if not checks["min_dimension"]:
        failure_reason = (
            f"low_resolution: min(H,W)={min(h,w)} < threshold {min_dimension}"
        )

    # --- Check 2: blur ---
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    blur_score = _compute_blur_score(gray)
    metrics["blur_score"] = blur_score
    checks["not_blurry"] = blur_score >= blur_threshold
    if not checks["not_blurry"] and failure_reason == "OK":
        failure_reason = (
            f"blurry: Laplacian_var={blur_score:.2f} < threshold {blur_threshold}"
        )

    # --- Check 3 & 4: luminance ---
    lum_stats = _compute_luminance_stats(rgb)
    metrics.update(lum_stats)
    mean_lum = lum_stats["mean_luminance"]

    checks["not_too_dark"] = mean_lum >= dark_threshold
    if not checks["not_too_dark"] and failure_reason == "OK":
        failure_reason = (
            f"too_dark: mean_L={mean_lum:.2f} < threshold {dark_threshold}"
        )

    checks["not_too_bright"] = mean_lum <= bright_threshold
    if not checks["not_too_bright"] and failure_reason == "OK":
        failure_reason = (
            f"too_bright: mean_L={mean_lum:.2f} > threshold {bright_threshold}"
        )

    passed = all(checks.values())
    return QualityResult(passed=passed, reason=failure_reason, metrics=metrics, checks=checks)


def check_roi_quality(
    roi_rgb: np.ndarray,
    coverage_fraction: float,
    blur_threshold: float = BLUR_THRESHOLD,
    dark_threshold: float = DARK_THRESHOLD,
    bright_threshold: float = BRIGHT_THRESHOLD,
    min_dimension: int = MIN_DIMENSION,
    min_roi_coverage: float = MIN_ROI_COVERAGE_FRACTION,
) -> QualityResult:
    """
    Run quality checks on the extracted ROI region.

    Includes all checks from check_image_quality() PLUS an ROI-coverage check.
    The coverage check is only available at this stage (after ROI extraction).

    Args:
        roi_rgb:            (H, W, 3) uint8 RGB array of the extracted ROI crop.
        coverage_fraction:  Fraction of mask pixels that were inside the ROI
                            (from ROIResult.coverage_fraction).
        blur_threshold:     Laplacian variance threshold.
        dark_threshold:     L-channel mean threshold for darkness.
        bright_threshold:   L-channel mean threshold for brightness.
        min_dimension:      Minimum acceptable shorter axis (pixels).
        min_roi_coverage:   Minimum acceptable ROI coverage fraction.

    Returns:
        QualityResult. If passed=False, `reason` explains the first failing check.
    """
    # Run the standard image checks on the ROI crop
    base_result = check_image_quality(
        roi_rgb,
        blur_threshold=blur_threshold,
        dark_threshold=dark_threshold,
        bright_threshold=bright_threshold,
        min_dimension=min_dimension,
    )

    # Add coverage check on top
    metrics = dict(base_result.metrics)
    checks = dict(base_result.checks)
    metrics["roi_coverage_fraction"] = coverage_fraction

    checks["roi_coverage"] = coverage_fraction >= min_roi_coverage
    failure_reason = base_result.reason

    if not checks["roi_coverage"] and failure_reason == "OK":
        failure_reason = (
            f"poor_roi_coverage: coverage={coverage_fraction:.4f} "
            f"< threshold {min_roi_coverage}"
        )

    passed = all(checks.values())
    return QualityResult(passed=passed, reason=failure_reason, metrics=metrics, checks=checks)


def check_image_from_path(
    raw_path: str,
    blur_threshold: float = BLUR_THRESHOLD,
    dark_threshold: float = DARK_THRESHOLD,
    bright_threshold: float = BRIGHT_THRESHOLD,
    min_dimension: int = MIN_DIMENSION,
) -> QualityResult:
    """
    Convenience wrapper: load a raw photo from disk and run quality checks.

    Uses the Phase 2 safe loader (PIL + EXIF rotation, OpenCV fallback for masks).
    Returns a QualityResult with passed=False if the file cannot be loaded.

    Args:
        raw_path: Path to the raw JPEG photo.

    Returns:
        QualityResult.
    """
    try:
        from src.data.validation import load_raw_photo, InvalidImageError
        rgb = load_raw_photo(raw_path, apply_exif_rotation=True)
    except Exception as e:
        return QualityResult(
            passed=False,
            reason=f"invalid_image: cannot load {raw_path}: {e}",
            metrics={},
            checks={"loadable": False},
        )

    result = check_image_quality(
        rgb,
        blur_threshold=blur_threshold,
        dark_threshold=dark_threshold,
        bright_threshold=bright_threshold,
        min_dimension=min_dimension,
    )
    return result
