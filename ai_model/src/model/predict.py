"""Run the Phase 4 CV pipeline and a saved Hb regressor on one image.

Provides the full structured screening output combining:
  - Image quality gate (image_quality_status, image_quality_score)
  - MC dropout uncertainty (hb_std_g_dl, confidence_interval_95)
  - Confidence calibration (confidence_status)
  - Decision layer (recommendation, recommendation_text)

All outputs are SCREENING ESTIMATES. This is NOT a medical diagnosis.
"""

import argparse
import json
from pathlib import Path
from typing import Optional

import torch

from src.vision.pipeline import process_subject
from src.vision.quality_gate import make_quality_gate
from .config import QUALITY_OVERRIDES, MODEL_DIR
from .confidence import ConfidenceCalibrator
from .decision import HbDecisionSystem, MODEL_VERSION
from .model import HbRegressor


# ---------------------------------------------------------------------------
# Default path for saved calibration parameters
# ---------------------------------------------------------------------------
_DEFAULT_CALIBRATION_PATH = str(MODEL_DIR / "confidence_calibration_params.json")


def _predict_with_dropout_uncertainty(model, image, device, mc_samples=25):
    """Return mean + std for Monte Carlo dropout uncertainty estimates."""
    if mc_samples <= 1:
        model.eval()
        with torch.no_grad():
            estimate = float(model(image).item())
        return estimate, 0.0

    was_training = model.training
    model.train()
    outputs = []
    with torch.no_grad():
        for _ in range(mc_samples):
            outputs.append(float(model(image).item()))
    model.train(was_training)
    tensor = torch.tensor(outputs, device=device, dtype=torch.float32)
    return float(tensor.mean().item()), float(tensor.std(unbiased=False).item())


def predict(raw_path, mask_path, model_path, subject_id="inference", device="cpu"):
    result = predict_with_confidence(raw_path, mask_path, model_path, subject_id, device, mc_samples=1)
    if result["image_quality_status"] == "REJECTED":
        return {
            "subject_id": subject_id,
            "image_quality_status": "REJECTED",
            "recommendation": result["recommendation"],
            "image_failure_reasons": result.get("image_failure_reasons", []),
        }
    return {
        "subject_id": subject_id,
        "image_quality_status": "ACCEPTED",
        "estimated_hb_g_dl": result["estimated_hb_g_dl"],
        "recommendation": result["recommendation"],
        "model_version": result["model_version"],
    }


def predict_with_confidence(
    raw_path: str,
    mask_path: str,
    model_path: str,
    subject_id: str = "inference",
    device: str = "cpu",
    mc_samples: int = 25,
    calibration_path: Optional[str] = None,
) -> dict:
    """
    Run a single prediction and return the full structured screening output.

    Returns
    -------
    Dict with keys:
        estimated_hb_g_dl       — Hb prediction in g/dL (None if rejected)
        hb_std_g_dl             — MC dropout std (None if rejected)
        confidence_interval_95  — [lower, upper] 95% CI (None if rejected)
        confidence_status       — HIGH_CONFIDENCE / MEDIUM_CONFIDENCE / LOW_CONFIDENCE
        image_quality_status    — ACCEPTED / REJECTED
        image_quality_score     — float in [0,1] — image quality (NOT medical confidence)
        image_failure_reasons   — list of rejection reasons (empty if accepted)
        recommendation          — RETAKE_IMAGE / CONFIRMATORY_TEST / SCREENING_ESTIMATE
        recommendation_text     — Human-readable recommendation
        model_version           — Model version string
        _disclaimer             — Medical safety disclaimer
    """
    # ------------------------------------------------------------------ #
    # Step 1: Run CV pipeline (quality check + ROI extraction)
    # ------------------------------------------------------------------ #
    pipeline_result = process_subject(
        subject_id, raw_path, mask_path, quality_overrides=QUALITY_OVERRIDES
    )

    # ------------------------------------------------------------------ #
    # Step 2: Image quality gate — structured output
    # ------------------------------------------------------------------ #
    quality_gate = make_quality_gate(QUALITY_OVERRIDES)

    if not pipeline_result.accepted:
        # Build quality gate result from pipeline rejection
        qg_result = {
            "quality_status": "REJECTED",
            "quality_score": 0.0,
            "failure_reasons": [pipeline_result.quality_report.get("reject_reason", "unknown_rejection")],
        }
    else:
        # Run quality gate on accepted image for structured output
        raw_q = pipeline_result.quality_report.get("raw_image_quality", {})
        coverage = (
            pipeline_result.roi_info.coverage_fraction
            if pipeline_result.roi_info else 0.0
        )
        # Reconstruct a simple rgb proxy for quality gate (pipeline already accepted it)
        # We use the quality metrics already computed by the pipeline
        metrics = raw_q.get("metrics", {}) if raw_q else {}
        checks = raw_q.get("checks", {}) if raw_q else {}
        n_checks = max(len(checks), 1)
        n_passed = sum(1 for v in checks.values() if v)
        base_score = float(n_passed / n_checks)
        blur = metrics.get("blur_score", 50.0)
        lum = metrics.get("mean_luminance", 128.0)
        blur_score = min(1.0, blur / 500.0)
        lum_score = 1.0 - abs(lum - 128.0) / 128.0
        quality_score = max(0.0, min(1.0, 0.5 * base_score + 0.3 * blur_score + 0.2 * lum_score))
        qg_result = {
            "quality_status": "ACCEPTED",
            "quality_score": quality_score,
            "failure_reasons": [],
        }

    # ------------------------------------------------------------------ #
    # Step 3: Model inference (if image accepted)
    # ------------------------------------------------------------------ #
    estimated_hb = None
    uncertainty = None

    if pipeline_result.accepted and pipeline_result.roi_tensor is not None:
        checkpoint = torch.load(model_path, map_location=device, weights_only=False)
        model = HbRegressor(
            pretrained=checkpoint.get("config", {}).get("pretrained", False),
            freeze_backbone=checkpoint.get("config", {}).get("freeze_backbone", False),
        ).to(device)
        model.load_state_dict(
            checkpoint["model_state_dict"] if "model_state_dict" in checkpoint else checkpoint
        )
        image = (
            torch.from_numpy(pipeline_result.roi_tensor.transpose(2, 0, 1))
            .unsqueeze(0).float().to(device)
        )
        raw_estimate, raw_std = _predict_with_dropout_uncertainty(
            model, image, device, mc_samples=max(1, int(mc_samples))
        )
        target_mean = checkpoint.get("config", {}).get("target_mean", 0.0)
        target_std = checkpoint.get("config", {}).get("target_std", 1.0)
        estimated_hb = raw_estimate * target_std + target_mean
        uncertainty = raw_std * target_std

    # ------------------------------------------------------------------ #
    # Step 4: Confidence calibration
    # ------------------------------------------------------------------ #
    calib_path = calibration_path or _DEFAULT_CALIBRATION_PATH
    if Path(calib_path).is_file():
        calibrator = ConfidenceCalibrator.load(calib_path)
    else:
        calibrator = ConfidenceCalibrator()

    # ------------------------------------------------------------------ #
    # Step 5: Decision system — final structured output
    # ------------------------------------------------------------------ #
    decision_system = HbDecisionSystem(calibrator)
    output = decision_system.decide(
        estimated_hb=estimated_hb,
        uncertainty=uncertainty if uncertainty is not None else 0.0,
        quality_status=qg_result["quality_status"],
        quality_score=qg_result["quality_score"],
        failure_reasons=qg_result["failure_reasons"],
        model_version=MODEL_VERSION,
    )

    # Add subject_id and pipeline quality report for downstream audit
    output["subject_id"] = subject_id
    output["pipeline_quality_report"] = pipeline_result.quality_report

    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True)
    parser.add_argument("--mask", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--subject-id", default="inference")
    parser.add_argument("--device", default="cpu", choices=("cpu", "cuda"))
    parser.add_argument(
        "--mc-samples", type=int, default=25,
        help="Monte Carlo dropout samples for uncertainty estimation"
    )
    parser.add_argument("--calibration", default=None, help="Path to calibration params JSON")
    args = parser.parse_args()
    if args.device == "cuda" and not torch.cuda.is_available():
        parser.error("--device cuda requested but CUDA is unavailable")
    result = predict_with_confidence(
        args.image, args.mask, args.model,
        args.subject_id, args.device, args.mc_samples, args.calibration
    )
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
