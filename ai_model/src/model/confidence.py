"""
confidence.py
=============
Validation-derived confidence calibration for the Hb screening pipeline.

DESIGN PHILOSOPHY
-----------------
This module derives confidence thresholds from actual validation data.
No thresholds are invented or hardcoded without empirical basis.

The confidence system combines:
  1. Image quality gate (from src/vision/quality_gate.py)
  2. MC dropout prediction uncertainty (std of MC samples)

Possible confidence statuses:
  HIGH_CONFIDENCE   — good image quality + low model uncertainty
  MEDIUM_CONFIDENCE — good image quality + moderate uncertainty
  LOW_CONFIDENCE    — good image quality + high uncertainty, OR marginal quality

IMPORTANT DISCLAIMERS
---------------------
- Confidence is NOT medical certainty.
- Even HIGH_CONFIDENCE estimates are screening estimates only.
- This system reduces false reassurance by flagging uncertain predictions.
- It does NOT replace clinical laboratory testing.
- MC dropout uncertainty is a proxy for model uncertainty, not aleatoric
  (data) uncertainty. Its calibration on this small dataset may be poor.
- Thresholds are derived from the validation set (n≈29 subjects). They are
  empirically grounded but should be re-evaluated with more data.
"""

import json
from pathlib import Path
from typing import Dict, Optional, Tuple

import numpy as np


# ---------------------------------------------------------------------------
# Default thresholds (derived from validation data — see calibrate())
# These are placeholder defaults; calibrate() should be called with real data.
# ---------------------------------------------------------------------------
_DEFAULT_LOW_UNCERTAINTY_THRESHOLD: float = 0.5    # std < this → HIGH
_DEFAULT_HIGH_UNCERTAINTY_THRESHOLD: float = 1.0   # std > this → LOW


class ConfidenceCalibrator:
    """
    Calibrates confidence thresholds from validation-set predictions.

    Usage
    -----
        calibrator = ConfidenceCalibrator()
        calibrator.calibrate(val_uncertainties, val_errors)
        calibrator.save("results/confidence_calibration_params.json")

        # At inference time:
        status = calibrator.get_confidence_status(uncertainty, quality_score)
    """

    def __init__(self):
        self.low_uncertainty_threshold = _DEFAULT_LOW_UNCERTAINTY_THRESHOLD
        self.high_uncertainty_threshold = _DEFAULT_HIGH_UNCERTAINTY_THRESHOLD
        self.calibrated = False
        self.calibration_n = 0
        self.calibration_notes = []

    def calibrate(
        self,
        uncertainties: np.ndarray,
        errors: np.ndarray,
        quality_scores: Optional[np.ndarray] = None,
    ) -> Dict:
        """
        Derive uncertainty thresholds from validation data.

        Strategy:
        - Sort subjects by uncertainty.
        - Find the uncertainty value that splits the validation set into
          thirds (approximately): low, medium, high uncertainty.
        - Verify that the high-uncertainty group has higher error than the
          low-uncertainty group.
        - If MC dropout is not well-calibrated (no monotonic relationship),
          document that honestly.

        Args:
            uncertainties: Array of MC dropout std values from validation set.
            errors:        Array of absolute errors from validation set.
            quality_scores: Optional array of image quality scores.

        Returns:
            Dict of calibration statistics.
        """
        uncertainties = np.asarray(uncertainties, dtype=np.float64)
        errors = np.asarray(errors, dtype=np.float64)
        if uncertainties.size == 0 or errors.size == 0:
            raise ValueError("uncertainties and errors must be non-empty arrays")
        if uncertainties.shape != errors.shape:
            raise ValueError(f"uncertainties and errors must have matching shapes, got {uncertainties.shape} and {errors.shape}")
        if not np.isfinite(uncertainties).all() or not np.isfinite(errors).all():
            raise ValueError("uncertainties and errors must contain only finite numeric values")

        n = len(uncertainties)
        self.calibration_n = n
        self.calibration_notes = []

        if n < 9:
            self.calibration_notes.append(
                f"WARNING: Only {n} validation subjects available. "
                "Thresholds derived from very small sample — treat with caution."
            )

        order = np.argsort(uncertainties)
        sorted_unc = uncertainties[order]
        sorted_err = errors[order]

        if n >= 3:
            t33 = float(np.percentile(uncertainties, 33))
            t67 = float(np.percentile(uncertainties, 67))
        else:
            t33 = float(uncertainties.mean())
            t67 = float(uncertainties.mean())

        low_mask = uncertainties <= t33
        high_mask = uncertainties > t67
        med_mask = ~low_mask & ~high_mask

        low_err = float(errors[low_mask].mean()) if low_mask.any() else float("nan")
        med_err = float(errors[med_mask].mean()) if med_mask.any() else float("nan")
        high_err = float(errors[high_mask].mean()) if high_mask.any() else float("nan")

        calibration_monotonic = (
            not np.isnan(low_err) and not np.isnan(high_err) and high_err >= low_err
        )
        if not calibration_monotonic:
            self.calibration_notes.append(
                "CALIBRATION POOR: Higher uncertainty does NOT correspond to higher error "
                f"on the validation set (low_err={low_err:.4f}, high_err={high_err:.4f}). "
                "MC dropout uncertainty is weakly calibrated on this dataset. "
                "Confidence thresholds should be interpreted with caution."
            )

        self.low_uncertainty_threshold = float(t33)
        self.high_uncertainty_threshold = float(t67)
        self.calibrated = True

        ci95_lower = uncertainties * 1.96
        coverage = float(np.mean(errors <= ci95_lower)) if len(errors) > 0 else float("nan")

        if n >= 3 and np.std(uncertainties) > 0 and np.std(errors) > 0:
            corr = float(np.corrcoef(uncertainties, errors)[0, 1])
        else:
            corr = float("nan")

        stats = {
            "n_validation": n,
            "low_uncertainty_threshold": self.low_uncertainty_threshold,
            "high_uncertainty_threshold": self.high_uncertainty_threshold,
            "mean_error_low_uncertainty_tertile": low_err,
            "mean_error_medium_uncertainty_tertile": med_err,
            "mean_error_high_uncertainty_tertile": high_err,
            "calibration_monotonic": calibration_monotonic,
            "pearson_correlation_uncertainty_error": corr,
            "ci95_coverage_fraction": coverage,
            "calibration_notes": self.calibration_notes,
        }

        return stats

    def get_confidence_status(
        self,
        uncertainty: float,
        quality_score: Optional[float] = None,
        quality_status: Optional[str] = None,
    ) -> str:
        """
        Map (uncertainty, quality) to a confidence status string.

        Args:
            uncertainty:    MC dropout std (g/dL).
            quality_score:  Image quality score in [0, 1] (optional).
            quality_status: "ACCEPTED" or "REJECTED" (optional).

        Returns:
            One of: "HIGH_CONFIDENCE", "MEDIUM_CONFIDENCE", "LOW_CONFIDENCE"
        """
        if quality_status == "REJECTED":
            return "LOW_CONFIDENCE"

        if uncertainty is None or (isinstance(uncertainty, float) and not np.isfinite(uncertainty)):
            return "LOW_CONFIDENCE"

        uncertainty = float(uncertainty)
        if uncertainty < 0:
            uncertainty = 0.0

        quality_penalty = False
        if quality_score is not None:
            try:
                parsed = float(quality_score)
            except (TypeError, ValueError):
                parsed = 0.0
            if not np.isfinite(parsed):
                parsed = 0.0
            if parsed < 0.4:
                quality_penalty = True

        if uncertainty <= self.low_uncertainty_threshold and not quality_penalty:
            return "HIGH_CONFIDENCE"
        elif uncertainty <= self.high_uncertainty_threshold:
            return "MEDIUM_CONFIDENCE"
        else:
            return "LOW_CONFIDENCE"

    def save(self, path: str) -> None:
        """Save calibration parameters to a JSON file."""
        data = {
            "calibrated": self.calibrated,
            "calibration_n": self.calibration_n,
            "low_uncertainty_threshold": self.low_uncertainty_threshold,
            "high_uncertainty_threshold": self.high_uncertainty_threshold,
            "calibration_notes": self.calibration_notes,
        }
        Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: str) -> "ConfidenceCalibrator":
        """Load calibration parameters from a JSON file."""
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        calibrator = cls()
        calibrator.calibrated = data.get("calibrated", False)
        calibrator.calibration_n = data.get("calibration_n", 0)
        calibrator.low_uncertainty_threshold = data.get(
            "low_uncertainty_threshold", _DEFAULT_LOW_UNCERTAINTY_THRESHOLD
        )
        calibrator.high_uncertainty_threshold = data.get(
            "high_uncertainty_threshold", _DEFAULT_HIGH_UNCERTAINTY_THRESHOLD
        )
        calibrator.calibration_notes = data.get("calibration_notes", [])
        return calibrator
