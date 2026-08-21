"""
quality_gate.py
===============
Structured Image Quality Gate for the anaemia screening pipeline.

This module provides a formal quality gate with structured output suitable
for downstream decision-making. It wraps the existing check_image_quality()
and check_roi_quality() functions from src/vision/quality.py and adds:

  - A composite quality_score (0.0–1.0, HIGHER = better image quality)
  - Structured failure_reasons list
  - Clear quality_status: "ACCEPTED" or "REJECTED"

IMPORTANT DISCLAIMER
--------------------
quality_score is an IMAGE QUALITY metric only.
It is NOT medical confidence.
It is NOT a clinical certainty estimate.
It does NOT measure the reliability of the Hb prediction.
It only measures whether the captured image is technically suitable for
processing (blur, brightness, resolution, ROI coverage).

Medical confidence and prediction uncertainty are handled separately by
src/model/confidence.py.
"""

from typing import Dict, List, Optional, Tuple
import numpy as np

from .quality import (
    check_image_quality,
    check_roi_quality,
    QualityResult,
    BLUR_THRESHOLD,
    DARK_THRESHOLD,
    BRIGHT_THRESHOLD,
    MIN_DIMENSION,
    MIN_ROI_COVERAGE_FRACTION,
)


class ImageQualityGate:
    """
    Structured image quality gate for conjunctiva anaemia screening images.

    Combines multiple quality checks into a single structured output with:
      - quality_status: "ACCEPTED" or "REJECTED"
      - quality_score: float in [0, 1] — image quality score (NOT medical confidence)
      - failure_reasons: list of human-readable rejection reasons
      - check_details: dict of individual check results

    Usage
    -----
        gate = ImageQualityGate()
        result = gate.check(rgb_image, coverage_fraction=0.05)
        if result["quality_status"] == "ACCEPTED":
            # proceed to inference
        else:
            print("Please retake image:", result["failure_reasons"])
    """

    def __init__(
        self,
        blur_threshold: float = BLUR_THRESHOLD,
        dark_threshold: float = DARK_THRESHOLD,
        bright_threshold: float = BRIGHT_THRESHOLD,
        min_dimension: int = MIN_DIMENSION,
        min_roi_coverage: float = MIN_ROI_COVERAGE_FRACTION,
    ):
        """
        Args:
            blur_threshold:   Laplacian variance threshold (below = too blurry).
            dark_threshold:   L-channel mean below = too dark.
            bright_threshold: L-channel mean above = too bright / overexposed.
            min_dimension:    Minimum acceptable shorter axis in pixels.
            min_roi_coverage: Minimum acceptable ROI coverage fraction.
        """
        self.blur_threshold = blur_threshold
        self.dark_threshold = dark_threshold
        self.bright_threshold = bright_threshold
        self.min_dimension = min_dimension
        self.min_roi_coverage = min_roi_coverage

    def check(
        self,
        rgb: np.ndarray,
        coverage_fraction: Optional[float] = None,
        roi_rgb: Optional[np.ndarray] = None,
    ) -> Dict:
        """
        Run all image quality checks and return a structured result.

        Args:
            rgb:               (H, W, 3) uint8 RGB array — full image or ROI.
            coverage_fraction: Optional ROI coverage fraction (0–1). If provided,
                               the ROI coverage check is included.
            roi_rgb:           Optional (H, W, 3) uint8 RGB array of the ROI crop.
                               If provided, ROI-specific quality checks are run.

        Returns:
            Dict with keys:
                quality_status:  "ACCEPTED" or "REJECTED"
                quality_score:   float in [0, 1] — image quality (NOT medical confidence)
                failure_reasons: list[str] — empty if accepted
                check_details:   dict of individual check results
                metrics:         dict of computed metric values
        """
        failure_reasons: List[str] = []
        check_details: Dict[str, bool] = {}
        all_metrics: Dict = {}

        # --- Guard: handle None / invalid input before passing to quality checks ---
        if rgb is None:
            return {
                "quality_status": "REJECTED",
                "quality_score": 0.0,
                "failure_reasons": ["INVALID_INPUT: image is None"],
                "check_details": {"valid_array": False},
                "metrics": {},
                "_disclaimer": (
                    "quality_score is an image quality metric only. "
                    "It is NOT medical confidence and NOT a clinical certainty estimate."
                ),
            }

        # --- Full image quality checks ---
        img_result = check_image_quality(
            rgb,
            blur_threshold=self.blur_threshold,
            dark_threshold=self.dark_threshold,
            bright_threshold=self.bright_threshold,
            min_dimension=self.min_dimension,
        )
        check_details.update({f"image_{k}": v for k, v in img_result.checks.items()})
        all_metrics.update({f"image_{k}": v for k, v in img_result.metrics.items()})

        if not img_result.checks.get("min_dimension", True):
            failure_reasons.append(
                f"LOW_RESOLUTION: image too small (min dimension {img_result.metrics.get('min_dimension')} px "
                f"< threshold {self.min_dimension} px)"
            )
        if not img_result.checks.get("not_blurry", True):
            failure_reasons.append(
                f"TOO_BLURRY: Laplacian variance {img_result.metrics.get('blur_score', 0):.2f} "
                f"< threshold {self.blur_threshold}"
            )
        if not img_result.checks.get("not_too_dark", True):
            failure_reasons.append(
                f"TOO_DARK: mean luminance {img_result.metrics.get('mean_luminance', 0):.1f} "
                f"< threshold {self.dark_threshold}"
            )
        if not img_result.checks.get("not_too_bright", True):
            failure_reasons.append(
                f"TOO_BRIGHT: mean luminance {img_result.metrics.get('mean_luminance', 0):.1f} "
                f"> threshold {self.bright_threshold}"
            )

        # --- ROI quality checks (if ROI available) ---
        if roi_rgb is not None and coverage_fraction is not None:
            roi_result = check_roi_quality(
                roi_rgb,
                coverage_fraction,
                blur_threshold=self.blur_threshold,
                dark_threshold=self.dark_threshold,
                bright_threshold=self.bright_threshold,
                min_dimension=self.min_dimension,
                min_roi_coverage=self.min_roi_coverage,
            )
            check_details.update({f"roi_{k}": v for k, v in roi_result.checks.items()})
            all_metrics.update({f"roi_{k}": v for k, v in roi_result.metrics.items()})

            if not roi_result.checks.get("roi_coverage", True):
                failure_reasons.append(
                    f"POOR_ROI_COVERAGE: coverage {coverage_fraction:.4f} "
                    f"< threshold {self.min_roi_coverage}"
                )
            if not roi_result.checks.get("not_blurry", True) and img_result.checks.get("not_blurry", True):
                # ROI is blurry even though full image is sharp — localised blur
                failure_reasons.append(
                    f"ROI_TOO_BLURRY: ROI Laplacian variance {roi_result.metrics.get('blur_score', 0):.2f} "
                    f"< threshold {self.blur_threshold}"
                )

        elif coverage_fraction is not None and coverage_fraction < self.min_roi_coverage:
            # Coverage check without roi_rgb
            check_details["roi_coverage"] = False
            failure_reasons.append(
                f"POOR_ROI_COVERAGE: coverage {coverage_fraction:.4f} "
                f"< threshold {self.min_roi_coverage}"
            )
            all_metrics["roi_coverage_fraction"] = coverage_fraction

        # --- ROI detection failure ---
        # Caller signals this by passing coverage_fraction=0.0
        if coverage_fraction is not None and coverage_fraction == 0.0:
            failure_reasons.append("ROI_DETECTION_FAILED: no ROI pixels found in mask")
            check_details["roi_detected"] = False

        # --- Compute composite quality_score ---
        # Each check contributes equally; score = fraction of passing checks
        # This is a simple heuristic. It is NOT a medical confidence score.
        n_checks = max(len(check_details), 1)
        n_passed = sum(1 for v in check_details.values() if v)
        quality_score = float(n_passed / n_checks)

        # Also weight blur and luminance into the score continuously
        blur = all_metrics.get("image_blur_score", self.blur_threshold)
        lum = all_metrics.get("image_mean_luminance", 128.0)

        blur_score = min(1.0, blur / (self.blur_threshold * 10))  # normalised blur contribution
        lum_score = 1.0 - abs(lum - 128.0) / 128.0  # distance from ideal mid-luminance
        quality_score = 0.5 * quality_score + 0.3 * blur_score + 0.2 * lum_score
        quality_score = float(max(0.0, min(1.0, quality_score)))

        status = "ACCEPTED" if len(failure_reasons) == 0 else "REJECTED"

        return {
            "quality_status": status,
            "quality_score": quality_score,
            "failure_reasons": failure_reasons,
            "check_details": check_details,
            "metrics": all_metrics,
            "_disclaimer": (
                "quality_score is an image quality metric only. "
                "It is NOT medical confidence and NOT a clinical certainty estimate."
            ),
        }

    def check_from_arrays(
        self,
        rgb: np.ndarray,
        coverage_fraction: float,
        roi_rgb: Optional[np.ndarray] = None,
    ) -> Dict:
        """Alias for check() with mandatory coverage_fraction."""
        return self.check(rgb, coverage_fraction=coverage_fraction, roi_rgb=roi_rgb)


def make_quality_gate(quality_overrides: Optional[Dict] = None) -> ImageQualityGate:
    """
    Factory function: create an ImageQualityGate with optional threshold overrides.

    Args:
        quality_overrides: Dict of threshold overrides, e.g. {"blur_threshold": 10.0}

    Returns:
        ImageQualityGate instance.
    """
    kwargs = {}
    if quality_overrides:
        mapping = {
            "blur_threshold": "blur_threshold",
            "dark_threshold": "dark_threshold",
            "bright_threshold": "bright_threshold",
            "min_dimension": "min_dimension",
            "min_roi_coverage": "min_roi_coverage",
        }
        for k, v in quality_overrides.items():
            if k in mapping:
                kwargs[mapping[k]] = v
    return ImageQualityGate(**kwargs)
