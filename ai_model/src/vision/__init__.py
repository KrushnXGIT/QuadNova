"""
src/vision/__init__.py
======================
Phase 3 — Computer Vision Pipeline package.

Public API:
    from src.vision.pipeline import process_subject, CVPipelineResult
    from src.vision.roi import extract_conjunctiva_roi, ROIResult
    from src.vision.quality import check_image_quality, QualityResult
    from src.vision.color_normalization import normalize_roi

Pipeline flow:
    Input Image
        ↓
    Image Quality Check       (vision/quality.py)
        ↓
    Conjunctiva ROI Extraction (vision/roi.py)
        ↓
    ROI Quality Check          (vision/quality.py)
        ↓
    Color Normalization        (vision/color_normalization.py)
        ↓
    Model-ready tensor         (vision/pipeline.py)

All components build on Phase 2's confirmed dataset findings:
  - Masks exist (RGBA, alpha>0 = ROI)
  - iCCP CRC defect in masks -> OpenCV only
  - EXIF rotation required before mask alignment
  - Scale factor recomputed per-subject (not hardcoded)
See CV_PIPELINE.md for full architecture documentation.
"""

from .pipeline import process_subject, CVPipelineResult  # noqa: F401
from .roi import extract_conjunctiva_roi, ROIResult  # noqa: F401
from .quality import check_image_quality, check_roi_quality, QualityResult  # noqa: F401
from .color_normalization import normalize_roi  # noqa: F401

__all__ = [
    "process_subject",
    "CVPipelineResult",
    "extract_conjunctiva_roi",
    "ROIResult",
    "check_image_quality",
    "check_roi_quality",
    "QualityResult",
    "normalize_roi",
]
