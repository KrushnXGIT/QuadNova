"""
decision.py
===========
Low-confidence decision system for the Hb anaemia screening pipeline.

This module implements the final decision layer that combines:
  1. Image quality (from ImageQualityGate)
  2. Model uncertainty (MC dropout std)
  3. Confidence calibration (ConfidenceCalibrator thresholds)

into a human-readable recommendation and structured output.

MEDICAL SAFETY DISCLAIMER
--------------------------
This is an AI-BASED ANAEMIA SCREENING PROTOTYPE.

It is NOT:
  - A definitive diagnosis
  - A replacement for a blood test
  - Clinically validated (no prospective clinical study has been conducted)

The system communicates SCREENING ESTIMATES only.
All output labeled:
  - "Estimated Hb" (not "Hb level")
  - "Screening estimate" (not "diagnosis")
  - "Consider confirmatory testing" for uncertain cases
  - "Please retake image" for poor image quality

The purpose of the decision layer is to PREVENT the system from claiming
certainty when its predictions are unreliable.
"""

from typing import Dict, Optional

from .confidence import ConfidenceCalibrator, _DEFAULT_LOW_UNCERTAINTY_THRESHOLD, _DEFAULT_HIGH_UNCERTAINTY_THRESHOLD

# ---------------------------------------------------------------------------
# Model version identifier — update when model is retrained
# ---------------------------------------------------------------------------
MODEL_VERSION = "hb_regressor_v1.0_mobilenetv3small"


class HbDecisionSystem:
    """
    Final decision layer for the Hb screening pipeline.

    Combines image quality + uncertainty + calibration into a recommendation.

    Recommendations
    ---------------
    RETAKE_IMAGE           — image quality failed; no prediction made
    CONFIRMATORY_TEST      — good image, but high uncertainty; screening estimate provided
    SCREENING_ESTIMATE     — good image, acceptable uncertainty; screening estimate provided

    Usage
    -----
        decision_system = HbDecisionSystem(calibrator)
        output = decision_system.decide(
            estimated_hb=11.5,
            uncertainty=0.8,
            quality_status="ACCEPTED",
            quality_score=0.72,
            failure_reasons=[],
        )
    """

    def __init__(self, calibrator: Optional[ConfidenceCalibrator] = None):
        if calibrator is None:
            calibrator = ConfidenceCalibrator()
        self.calibrator = calibrator

    def decide(
        self,
        estimated_hb: Optional[float],
        uncertainty: Optional[float],
        quality_status: str,
        quality_score: float,
        failure_reasons: list,
        model_version: str = MODEL_VERSION,
    ) -> Dict:
        """
        Produce the final structured screening output.

        Args:
            estimated_hb:    Hb prediction in g/dL (None if image rejected).
            uncertainty:     MC dropout std in g/dL (None if image rejected).
            quality_status:  "ACCEPTED" or "REJECTED" from ImageQualityGate.
            quality_score:   Float in [0, 1] — image quality score (NOT medical confidence).
            failure_reasons: List of failure reasons from ImageQualityGate.
            model_version:   Model version string.

        Returns:
            Dict with the full structured screening output.
        """
        if quality_status == "REJECTED":
            return {
                "estimated_hb_g_dl": None,
                "hb_std_g_dl": None,
                "confidence_interval_95": None,
                "confidence_status": "LOW_CONFIDENCE",
                "image_quality_status": "REJECTED",
                "image_quality_score": round(quality_score, 4),
                "image_failure_reasons": failure_reasons,
                "recommendation": "RETAKE_IMAGE",
                "recommendation_text": (
                    "The image quality is insufficient for screening. "
                    "Please retake the photo: ensure the eye is well-lit, in focus, "
                    "and the lower eyelid is everted to show the conjunctiva clearly."
                ),
                "model_version": model_version,
                "_disclaimer": (
                    "AI-based anaemia screening prototype. "
                    "Not a diagnosis. Not a replacement for blood testing."
                ),
            }

        if estimated_hb is None or uncertainty is None:
            return {
                "estimated_hb_g_dl": None,
                "hb_std_g_dl": None,
                "confidence_interval_95": None,
                "confidence_status": "LOW_CONFIDENCE",
                "image_quality_status": quality_status,
                "image_quality_score": round(float(quality_score), 4),
                "image_failure_reasons": failure_reasons,
                "recommendation": "CONFIRMATORY_TEST_RECOMMENDED",
                "recommendation_text": (
                    "Prediction is unavailable because the model could not produce a stable estimate. "
                    "A confirmatory blood test is recommended before any clinical decision."
                ),
                "model_version": model_version,
                "_disclaimer": (
                    "AI-based anaemia screening prototype. "
                    "Not a diagnosis. Not a replacement for blood testing. "
                    "Not clinically validated."
                ),
            }

        eff_uncertainty = float(uncertainty)
        eff_hb = float(estimated_hb)
        if not (float("-inf") < eff_uncertainty < float("inf")):
            eff_uncertainty = 0.0
        if not (float("-inf") < eff_hb < float("inf")):
            eff_hb = 0.0

        confidence_status = self.calibrator.get_confidence_status(
            eff_uncertainty,
            quality_score=quality_score,
            quality_status=quality_status,
        )

        ci_lower = round(eff_hb - 1.96 * eff_uncertainty, 2)
        ci_upper = round(eff_hb + 1.96 * eff_uncertainty, 2)

        if confidence_status == "HIGH_CONFIDENCE":
            recommendation = "SCREENING_ESTIMATE"
            recommendation_text = (
                f"Estimated Hb: {eff_hb:.1f} g/dL (screening estimate, ±{eff_uncertainty:.2f} g/dL). "
                "This is a screening estimate only. Confirm with a blood test for clinical decisions."
            )
        elif confidence_status == "MEDIUM_CONFIDENCE":
            recommendation = "SCREENING_ESTIMATE_LOW_CONFIDENCE"
            recommendation_text = (
                f"Estimated Hb: {eff_hb:.1f} g/dL (low-confidence screening estimate, ±{eff_uncertainty:.2f} g/dL). "
                "Uncertainty is moderate. Consider confirmatory testing before clinical decisions."
            )
        else:  # LOW_CONFIDENCE
            recommendation = "CONFIRMATORY_TEST_RECOMMENDED"
            recommendation_text = (
                f"Estimated Hb: {eff_hb:.1f} g/dL (very uncertain estimate, ±{eff_uncertainty:.2f} g/dL). "
                "Prediction uncertainty is high. "
                "A confirmatory blood test is strongly recommended before any clinical decision."
            )

        return {
            "estimated_hb_g_dl": round(eff_hb, 2),
            "hb_std_g_dl": round(eff_uncertainty, 4),
            "confidence_interval_95": [ci_lower, ci_upper],
            "confidence_status": confidence_status,
            "image_quality_status": quality_status,
            "image_quality_score": round(quality_score, 4),
            "image_failure_reasons": failure_reasons,
            "recommendation": recommendation,
            "recommendation_text": recommendation_text,
            "model_version": model_version,
            "_disclaimer": (
                "AI-based anaemia screening prototype. "
                "Not a diagnosis. Not a replacement for blood testing. "
                "Not clinically validated."
            ),
        }


def make_decision_system(calibrator_path: Optional[str] = None) -> HbDecisionSystem:
    """
    Factory: create an HbDecisionSystem, optionally loading calibration from file.

    Args:
        calibrator_path: Path to calibration JSON (from ConfidenceCalibrator.save()).
                         If None, uses default uncalibrated thresholds.

    Returns:
        HbDecisionSystem instance.
    """
    if calibrator_path is not None:
        from pathlib import Path as _Path
        if _Path(calibrator_path).is_file():
            calibrator = ConfidenceCalibrator.load(calibrator_path)
            return HbDecisionSystem(calibrator)

    return HbDecisionSystem(calibrator=None)
