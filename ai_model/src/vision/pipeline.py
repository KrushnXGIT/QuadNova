"""
pipeline.py
===========
CV Pipeline Orchestrator — Phase 3.

This is the primary entry point for Account 4 (model training phase) to obtain
a quality-checked, ROI-extracted, colour-normalised image tensor from a raw
subject file pair.

Pipeline flow
-------------
    Input: (raw_path, mask_path)
        ↓
    1. Image Quality Check (on full raw image)
        ↓  reject if failed → CVPipelineResult(accepted=False)
    2. Conjunctiva ROI Extraction (mask-guided)
        ↓  reject if ROI is empty / coverage too low
    3. ROI Quality Check (on the cropped ROI)
        ↓  reject if blurry / too dark / too bright
    4. Color Normalization (on the ROI)
        ↓
    5. Resize to model input size
        ↓
    Output: CVPipelineResult(accepted=True, ...)

All rejection reasons are stored in CVPipelineResult.quality_report for
downstream audit. Rejected images are NOT silently dropped — the caller
receives a complete record.

Design decisions (traced to dataset findings)
---------------------------------------------
- Quality check on the FULL image first, before spending time on ROI extraction.
  This catches blown-out, near-black, or truncated images cheaply.
- Quality check also applied on the ROI: the full image can pass while the ROI
  itself is blurry (e.g., motion blur localised to the centre of frame).
- Colour normalization applied to the ROI AFTER extraction: applying it to the
  full image before cropping would let the background (skin, eyelashes, etc.)
  influence the normalization statistics, potentially corrupting the ROI signal.
- All thresholds are passed through from quality.py constants and are overridable.
  They are NOT clinically validated — they are heuristic guards only.

Usage (Account 4)
-----------------
    from src.vision.pipeline import process_subject, CVPipelineResult

    result: CVPipelineResult = process_subject(
        subject_id = "20200118_164733",
        raw_path   = "data/raw/20200118_164733.jpg",
        mask_path  = "data/raw/20200118_164733_forniceal_palpebral.png",
        norm_method = "clahe",          # or "gray_world", "reinhard", "none"
        output_size = (224, 224),       # target H×W for model input
    )

    if result.accepted:
        # result.roi_tensor is (H, W, 3) float32 — ready for model
        # result.image_tensor is (H, W, 3) float32 — full image (normalised)
        pass
    else:
        print(result.quality_report["reject_reason"])
"""

import logging
import time
from typing import Dict, NamedTuple, Optional, Tuple

import cv2
import numpy as np

from src.data.validation import load_raw_photo, InvalidImageError
from src.data import config as data_config
from .roi import extract_conjunctiva_roi, ROIResult
from .quality import check_image_quality, check_roi_quality, QualityResult
from .color_normalization import normalize_roi

logger = logging.getLogger(__name__)

# Default model input size — matches Phase 2 config.MODEL_INPUT_SIZE
DEFAULT_OUTPUT_SIZE: Tuple[int, int] = data_config.MODEL_INPUT_SIZE  # (224, 224)

# Default color normalization method
DEFAULT_NORM_METHOD: str = "clahe"


class CVPipelineResult(NamedTuple):
    """
    Complete result of the CV pipeline for one subject.

    Attributes:
        subject_id:     The YYYYMMDD_HHMMSS subject identifier.
        accepted:       True if the image passed all quality checks and was
                        processed successfully. False if rejected at any stage.
        image_tensor:   (H, W, 3) float32 RGB array — full image (EXIF-corrected,
                        resized, normalised). None if accepted=False.
        roi_tensor:     (H, W, 3) float32 RGB array — extracted conjunctiva ROI
                        (quality-checked, normalised, resized). None if accepted=False.
        roi_info:       ROIResult with bbox, coverage_fraction, mask_variant, raw_shape.
                        None if ROI extraction failed.
        quality_report: Dict containing quality check results for each pipeline stage:
                        {
                          "raw_image_quality": QualityResult._asdict(),
                          "roi_quality":       QualityResult._asdict() or None,
                          "reject_reason":     str or "accepted",
                          "timing_ms":         float,
                          "norm_method":       str,
                          "output_size":       [H, W],
                        }
    """
    subject_id: str
    accepted: bool
    image_tensor: Optional[np.ndarray]
    roi_tensor: Optional[np.ndarray]
    roi_info: Optional[ROIResult]
    quality_report: Dict


def _resize_to_model(arr_float32: np.ndarray, output_size: Tuple[int, int]) -> np.ndarray:
    """
    Resize a (H, W, 3) float32 [0,1] array to output_size (H_out, W_out).
    Uses INTER_AREA for downscaling, INTER_LINEAR for upscaling.
    """
    h_out, w_out = output_size
    h_in, w_in = arr_float32.shape[:2]
    interp = cv2.INTER_AREA if (h_out * w_out < h_in * w_in) else cv2.INTER_LINEAR
    return cv2.resize(arr_float32, (w_out, h_out), interpolation=interp)


def _make_rejection(
    subject_id: str,
    reason: str,
    raw_quality: Optional[QualityResult],
    roi_quality: Optional[QualityResult],
    roi_info: Optional[ROIResult],
    norm_method: str,
    output_size: Tuple[int, int],
    t_start: float,
) -> CVPipelineResult:
    """Build a rejection CVPipelineResult."""
    report = {
        "raw_image_quality": raw_quality._asdict() if raw_quality else None,
        "roi_quality": roi_quality._asdict() if roi_quality else None,
        "reject_reason": reason,
        "timing_ms": round((time.time() - t_start) * 1000, 2),
        "norm_method": norm_method,
        "output_size": list(output_size),
    }
    logger.warning("Subject %s REJECTED: %s", subject_id, reason)
    return CVPipelineResult(
        subject_id=subject_id,
        accepted=False,
        image_tensor=None,
        roi_tensor=None,
        roi_info=roi_info,
        quality_report=report,
    )


def process_subject(
    subject_id: str,
    raw_path: str,
    mask_path: str,
    norm_method: str = DEFAULT_NORM_METHOD,
    output_size: Tuple[int, int] = DEFAULT_OUTPUT_SIZE,
    mask_variant: str = "forniceal_palpebral",
    skip_raw_quality_check: bool = False,
    skip_roi_quality_check: bool = False,
    quality_overrides: Optional[Dict] = None,
) -> CVPipelineResult:
    """
    Run the complete CV pipeline for one subject.

    Steps:
        1. Load raw image (EXIF-corrected).
        2. Quality check on full raw image.
        3. Extract conjunctiva ROI (mask-guided).
        4. Quality check on ROI.
        5. Colour normalization on ROI.
        6. Resize both full image and ROI to output_size.
        7. Return CVPipelineResult.

    Args:
        subject_id:             Subject identifier (for logging/reporting).
        raw_path:               Path to the raw JPEG.
        mask_path:              Path to the RGBA PNG mask.
        norm_method:            Color normalization method: 'clahe' (default),
                                'gray_world', 'reinhard', 'zscore', or 'none'.
        output_size:            (H, W) target size for both tensors. Default: (224, 224).
        mask_variant:           Which mask variant this mask_path represents.
        skip_raw_quality_check: If True, skip quality check on the full raw image.
        skip_roi_quality_check: If True, skip quality check on the ROI.
        quality_overrides:      Dict of quality threshold overrides, e.g.:
                                {"blur_threshold": 30.0, "min_roi_coverage": 0.005}

    Returns:
        CVPipelineResult.
    """
    t_start = time.time()
    q_kwargs = quality_overrides or {}

    # ------------------------------------------------------------------
    # Step 1: Load raw image
    # ------------------------------------------------------------------
    try:
        raw_rgb = load_raw_photo(str(raw_path), apply_exif_rotation=True)
    except (InvalidImageError, Exception) as e:
        return _make_rejection(
            subject_id, f"invalid_image: {e}",
            None, None, None, norm_method, output_size, t_start
        )

    # ------------------------------------------------------------------
    # Step 2: Quality check on raw image
    # ------------------------------------------------------------------
    raw_quality = check_image_quality(raw_rgb, **{
        k: v for k, v in q_kwargs.items()
        if k in ("blur_threshold", "dark_threshold", "bright_threshold", "min_dimension")
    })

    if not skip_raw_quality_check and not raw_quality.passed:
        return _make_rejection(
            subject_id,
            f"raw_quality_fail: {raw_quality.reason}",
            raw_quality, None, None, norm_method, output_size, t_start
        )

    # ------------------------------------------------------------------
    # Step 3: ROI extraction
    # ------------------------------------------------------------------
    try:
        roi_info = extract_conjunctiva_roi(
            str(raw_path), str(mask_path), mask_variant=mask_variant
        )
    except (FileNotFoundError, ValueError, Exception) as e:
        return _make_rejection(
            subject_id,
            f"roi_extraction_fail: {e}",
            raw_quality, None, None, norm_method, output_size, t_start
        )

    # ------------------------------------------------------------------
    # Step 4: Quality check on ROI
    # ------------------------------------------------------------------
    roi_quality = check_roi_quality(
        roi_info.roi_rgb,
        roi_info.coverage_fraction,
        **{
            k: v for k, v in q_kwargs.items()
            if k in (
                "blur_threshold", "dark_threshold", "bright_threshold",
                "min_dimension", "min_roi_coverage"
            )
        }
    )

    if not skip_roi_quality_check and not roi_quality.passed:
        return _make_rejection(
            subject_id,
            f"roi_quality_fail: {roi_quality.reason}",
            raw_quality, roi_quality, roi_info, norm_method, output_size, t_start
        )

    # ------------------------------------------------------------------
    # Step 5: Color normalization on ROI
    # ------------------------------------------------------------------
    try:
        roi_normalised = normalize_roi(roi_info.roi_rgb, method=norm_method)
    except Exception as e:
        return _make_rejection(
            subject_id,
            f"normalization_fail: {e}",
            raw_quality, roi_quality, roi_info, norm_method, output_size, t_start
        )

    # ------------------------------------------------------------------
    # Step 6: Resize to model input size
    # ------------------------------------------------------------------
    # Full image: normalize first (simple [0,1] scaling, no CLAHE)
    from .color_normalization import normalize_roi as _norm
    image_normalised = _norm(raw_rgb, method="none")  # [0,1] float32, no CLAHE on full image
    image_tensor = _resize_to_model(image_normalised, output_size)
    roi_tensor = _resize_to_model(roi_normalised, output_size)

    # ------------------------------------------------------------------
    # Step 7: Build result
    # ------------------------------------------------------------------
    elapsed_ms = round((time.time() - t_start) * 1000, 2)
    report = {
        "raw_image_quality": raw_quality._asdict(),
        "roi_quality": roi_quality._asdict(),
        "reject_reason": "accepted",
        "timing_ms": elapsed_ms,
        "norm_method": norm_method,
        "output_size": list(output_size),
    }

    logger.debug(
        "Subject %s accepted in %.1f ms — ROI coverage=%.4f, blur=%.2f",
        subject_id,
        elapsed_ms,
        roi_info.coverage_fraction,
        raw_quality.metrics.get("blur_score", float("nan")),
    )

    return CVPipelineResult(
        subject_id=subject_id,
        accepted=True,
        image_tensor=image_tensor,
        roi_tensor=roi_tensor,
        roi_info=roi_info,
        quality_report=report,
    )


def batch_process(
    subject_records: list,
    norm_method: str = DEFAULT_NORM_METHOD,
    output_size: Tuple[int, int] = DEFAULT_OUTPUT_SIZE,
    raw_dir: str = ".",
    mask_dir: Optional[str] = None,
) -> Tuple[list, dict]:
    """
    Run process_subject() over a batch of subjects from the Phase 2 matching records.

    Args:
        subject_records: List of dicts with keys: subject_id, raw_photo,
                         mask_forniceal_palpebral (as returned by Phase 2
                         scan_raw_data_dir()).
        norm_method:     Normalization method to apply.
        output_size:     Model input (H, W).
        raw_dir:         Directory containing raw files (defaults to '.').
        mask_dir:        Directory containing mask files. If None, uses raw_dir.

    Returns:
        (results, batch_summary) where:
          results:       List of CVPipelineResult, one per subject.
          batch_summary: Dict with accepted/rejected counts and per-reason breakdown.
    """
    import os
    if mask_dir is None:
        mask_dir = raw_dir

    results = []
    rejection_reasons = {}

    for rec in subject_records:
        sid = rec.get("subject_id") or rec.get("subject_id_str", "unknown")
        raw_file = rec.get("raw_photo")
        mask_file = rec.get("mask_forniceal_palpebral")

        if not raw_file or not mask_file:
            reason = "missing_raw_or_mask"
            rejection_reasons[reason] = rejection_reasons.get(reason, 0) + 1
            results.append(CVPipelineResult(
                subject_id=sid, accepted=False,
                image_tensor=None, roi_tensor=None, roi_info=None,
                quality_report={"reject_reason": reason}
            ))
            continue

        raw_path = os.path.join(raw_dir, raw_file)
        mask_path = os.path.join(mask_dir, mask_file)

        result = process_subject(
            subject_id=sid,
            raw_path=raw_path,
            mask_path=mask_path,
            norm_method=norm_method,
            output_size=output_size,
        )
        results.append(result)
        if not result.accepted:
            r = result.quality_report.get("reject_reason", "unknown")
            rejection_reasons[r] = rejection_reasons.get(r, 0) + 1

    n_accepted = sum(1 for r in results if r.accepted)
    batch_summary = {
        "total": len(results),
        "accepted": n_accepted,
        "rejected": len(results) - n_accepted,
        "acceptance_rate": n_accepted / len(results) if results else 0.0,
        "rejection_reasons": rejection_reasons,
        "norm_method": norm_method,
        "output_size": list(output_size),
    }

    logger.info(
        "Batch complete: %d/%d accepted (%.1f%%)",
        n_accepted, len(results), 100 * batch_summary["acceptance_rate"]
    )
    return results, batch_summary
