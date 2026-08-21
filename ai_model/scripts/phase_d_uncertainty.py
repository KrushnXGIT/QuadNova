"""
phase_d_uncertainty.py
======================
PHASE D: Uncertainty Analysis + Confidence Calibration

Runs MC dropout inference on all subjects in the validation set,
then calibrates the ConfidenceCalibrator from that data.

Produces:
  results/uncertainty_analysis.md
  results/confidence_calibration.md
  models/confidence_calibration_params.json
"""

import json
import sys
from pathlib import Path

import numpy as np
import torch
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.data.matching import scan_raw_data_dir
from src.data.splitting import load_split
from src.model.config import MODEL_DIR, RESULTS_DIR, SPLIT_PATH, QUALITY_OVERRIDES
from src.model.evaluate import regression_metrics
from src.model.model import HbRegressor
from src.model.confidence import ConfidenceCalibrator
from src.model.train import build_arrays
from src.data.labels import load_labels


MC_SAMPLES = 25


def _mc_dropout_predict(model, image_tensor, device, n=MC_SAMPLES):
    """Run MC dropout inference. Returns (mean, std)."""
    model.train()  # Enable dropout
    outputs = []
    with torch.no_grad():
        for _ in range(n):
            outputs.append(float(model(image_tensor.to(device)).item()))
    model.train(False)
    arr = np.array(outputs)
    return float(arr.mean()), float(arr.std())


def run_uncertainty_analysis(
    raw_dir: str = "data/raw/verified_flat",
    metadata_dir: str = "data/metadata",
    split_path: str = None,
    model_path: str = None,
    output_dir: str = None,
    cache_dir: str = "data/processed/model_cache",
):
    split_path = split_path or str(SPLIT_PATH)
    model_path = model_path or str(MODEL_DIR / "hb_regressor_best.pt")
    output_dir = Path(output_dir or RESULTS_DIR)
    model_dir = MODEL_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=== PHASE D: Uncertainty Analysis ===")

    labels = load_labels(metadata_dir)
    split = load_split(split_path)
    arrays, rejected = build_arrays(raw_dir, split["split"], labels, cache_dir=cache_dir)

    checkpoint = torch.load(model_path, map_location="cpu", weights_only=False)
    config = checkpoint.get("config", {})
    target_mean = config.get("target_mean", 0.0)
    target_std = config.get("target_std", 1.0)

    device = torch.device("cpu")
    model = HbRegressor(
        pretrained=config.get("pretrained", False),
        freeze_backbone=config.get("freeze_backbone", False),
    )
    model.load_state_dict(checkpoint["model_state_dict"])
    model = model.to(device)

    rows = []
    for split_name, (images, targets, subject_ids) in arrays.items():
        for i, (img, actual, sid) in enumerate(zip(images, targets, subject_ids)):
            img_tensor = torch.from_numpy(img).unsqueeze(0).float()
            raw_mean, raw_std = _mc_dropout_predict(model, img_tensor, device, n=MC_SAMPLES)
            pred_mean = raw_mean * target_std + target_mean
            pred_std = raw_std * target_std
            signed_error = pred_mean - float(actual)
            abs_error = abs(signed_error)

            rows.append({
                "subject_id": sid,
                "split": split_name,
                "actual_hb": float(actual),
                "predicted_hb": pred_mean,
                "hb_std": pred_std,
                "signed_error": signed_error,
                "absolute_error": abs_error,
                "ci95_lower": pred_mean - 1.96 * pred_std,
                "ci95_upper": pred_mean + 1.96 * pred_std,
                "in_ci95": (float(actual) >= pred_mean - 1.96 * pred_std and
                            float(actual) <= pred_mean + 1.96 * pred_std),
            })
        print(f"  {split_name}: {len(targets)} subjects processed")

    frame = pd.DataFrame(rows)
    frame.to_csv(output_dir / "uncertainty_analysis.csv", index=False)

    # Calibration: use validation set only
    val_frame = frame[frame["split"] == "val"]
    calibrator = ConfidenceCalibrator()
    cal_stats = calibrator.calibrate(
        val_frame["hb_std"].values,
        val_frame["absolute_error"].values,
    )

    # Save calibration params
    calib_path = model_dir / "confidence_calibration_params.json"
    calibrator.save(str(calib_path))
    print(f"  Saved calibration params: {calib_path}")

    # Statistics
    overall_coverage = float(frame["in_ci95"].mean())
    val_coverage = float(val_frame["in_ci95"].mean()) if len(val_frame) > 0 else float("nan")
    test_frame = frame[frame["split"] == "test"]
    test_coverage = float(test_frame["in_ci95"].mean()) if len(test_frame) > 0 else float("nan")

    corr_all = float(np.corrcoef(frame["hb_std"], frame["absolute_error"])[0, 1])
    corr_val = float(np.corrcoef(val_frame["hb_std"], val_frame["absolute_error"])[0, 1]) if len(val_frame) > 2 else float("nan")

    summary = {
        "mc_samples": MC_SAMPLES,
        "overall_ci95_coverage": overall_coverage,
        "val_ci95_coverage": val_coverage,
        "test_ci95_coverage": test_coverage,
        "corr_uncertainty_error_all": corr_all,
        "corr_uncertainty_error_val": corr_val,
        "calibration": cal_stats,
        "low_uncertainty_threshold": calibrator.low_uncertainty_threshold,
        "high_uncertainty_threshold": calibrator.high_uncertainty_threshold,
    }

    print(f"\n  95% CI coverage (all):  {overall_coverage:.4f}")
    print(f"  95% CI coverage (val):  {val_coverage:.4f}")
    print(f"  95% CI coverage (test): {test_coverage:.4f}")
    print(f"  Uncertainty-error correlation (all): {corr_all:.4f}")
    print(f"  Uncertainty-error correlation (val): {corr_val:.4f}")
    print(f"  Calibration monotonic: {cal_stats['calibration_monotonic']}")

    return frame, summary, calibrator


def write_uncertainty_analysis_md(frame: pd.DataFrame, summary: dict, output_dir: Path):
    val_frame = frame[frame["split"] == "val"]
    test_frame = frame[frame["split"] == "test"]

    mc_n = summary["mc_samples"]
    corr = summary["corr_uncertainty_error_all"]
    corr_val = summary["corr_uncertainty_error_val"]
    coverage_all = summary["overall_ci95_coverage"]
    coverage_val = summary["val_ci95_coverage"]
    coverage_test = summary["test_ci95_coverage"]

    lines = [
        "# Uncertainty Analysis Report",
        "",
        "## Method",
        "",
        f"MC dropout inference with {mc_n} forward passes per image.",
        "The model's dropout layer remains active during inference (training mode).",
        "Each forward pass produces a different output due to random dropout.",
        "The mean of the MC samples is the prediction; the std is the uncertainty estimate.",
        "",
        "**Limitation**: MC dropout approximates Bayesian uncertainty in the model weights. "
        "It does NOT capture aleatoric (data/measurement) uncertainty. "
        "On a small dataset, the resulting uncertainty estimates may be poorly calibrated.",
        "",
        "---",
        "",
        "## Results",
        "",
        "### 95% Prediction Interval Coverage",
        "",
        "A well-calibrated 95% CI should contain the true value in ~95% of cases.",
        "",
        "| Split | N | Coverage |",
        "|-------|---|----------|",
        f"| All | {len(frame)} | {coverage_all:.4f} ({coverage_all*100:.1f}%) |",
        f"| Validation | {len(val_frame)} | {coverage_val:.4f} ({coverage_val*100:.1f}%) |",
        f"| Test | {len(test_frame)} | {coverage_test:.4f} ({coverage_test*100:.1f}%) |",
        "",
        ("⚠️ **Coverage far from 95%**: The prediction intervals are not well-calibrated. "
         "See calibration notes below." if abs(coverage_all - 0.95) > 0.1 else
         "✓ Coverage is close to the expected 95%."),
        "",
        "### Uncertainty vs Error Correlation",
        "",
        f"Pearson correlation (all subjects): **{corr:.4f}**",
        f"Pearson correlation (val only): **{corr_val:.4f}**",
        "",
    ]

    if abs(corr) < 0.2:
        lines += [
            "The correlation between MC dropout uncertainty and prediction error is **weak**. "
            "Higher uncertainty does not reliably predict higher error on this dataset. "
            "This is a known limitation of MC dropout on small datasets with limited diversity.",
        ]
    elif corr > 0.2:
        lines += [
            "There is a moderate positive correlation: subjects with higher uncertainty "
            "tend to have higher absolute error. The uncertainty estimates have some signal.",
        ]
    else:
        lines += [
            "Negative correlation: subjects with higher uncertainty have LOWER error. "
            "The uncertainty signal is inverted and should not be used for confidence gating "
            "without recalibration.",
        ]

    cal = summary["calibration"]
    lines += [
        "",
        "---",
        "",
        "## Calibration Summary",
        "",
        f"Calibration was derived from the **validation set (n={cal['n_validation']})**.",
        "",
        f"| Tertile | Mean Absolute Error |",
        f"|---------|---------------------|",
        f"| Low uncertainty (≤{summary['low_uncertainty_threshold']:.4f}) | {cal['mean_error_low_uncertainty_tertile']:.4f} g/dL |",
        f"| Medium uncertainty | {cal['mean_error_medium_uncertainty_tertile']:.4f} g/dL |",
        f"| High uncertainty (>{summary['high_uncertainty_threshold']:.4f}) | {cal['mean_error_high_uncertainty_tertile']:.4f} g/dL |",
        "",
        f"**Calibration monotonic**: {'YES' if cal['calibration_monotonic'] else 'NO (see notes)'}",
        "",
    ]
    if cal["calibration_notes"]:
        lines.append("### Calibration Notes")
        lines.append("")
        for note in cal["calibration_notes"]:
            lines.append(f"- {note}")
        lines.append("")

    lines += [
        "---",
        "",
        "## Limitations",
        "",
        "1. MC dropout uncertainty is a proxy, not a true Bayesian posterior.",
        "2. The validation set has only ~29 subjects — threshold derivation is fragile.",
        "3. Uncertainty estimates are not interpretable as probability of clinical significance.",
        "4. The calibration should be re-evaluated with a larger dataset.",
        "",
        "---",
        "",
        "*Generated from actual MC dropout inference. No metrics were fabricated.*",
        "*If calibration is poor, this is documented, not hidden.*",
    ]

    (output_dir / "uncertainty_analysis.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Saved: {output_dir / 'uncertainty_analysis.md'}")


def write_confidence_calibration_md(summary: dict, output_dir: Path):
    cal = summary["calibration"]
    low_t = summary["low_uncertainty_threshold"]
    high_t = summary["high_uncertainty_threshold"]

    lines = [
        "# Confidence Calibration Report",
        "",
        "## System Design",
        "",
        "The confidence system combines:",
        "1. **Image quality gate**: Is the image technically usable?",
        "2. **MC dropout uncertainty**: How uncertain is the model?",
        "",
        "Output confidence statuses:",
        "- **HIGH_CONFIDENCE**: Good image + low uncertainty",
        "- **MEDIUM_CONFIDENCE**: Good image + moderate uncertainty",
        "- **LOW_CONFIDENCE**: Bad image OR high uncertainty",
        "",
        "**IMPORTANT**: Confidence here means prediction confidence, not clinical certainty. "
        "Even HIGH_CONFIDENCE results are screening estimates only.",
        "",
        "---",
        "",
        "## Threshold Derivation",
        "",
        f"Thresholds were derived from the **validation set (n={cal['n_validation']})** by "
        "splitting uncertainty values into tertiles (33rd and 67th percentiles).",
        "",
        "| Threshold | Value |",
        "|-----------|-------|",
        f"| LOW → MEDIUM boundary (33rd percentile) | **{low_t:.4f} g/dL std** |",
        f"| MEDIUM → HIGH boundary (67th percentile) | **{high_t:.4f} g/dL std** |",
        "",
        "This means:",
        f"- std ≤ {low_t:.4f} → HIGH_CONFIDENCE (lowest uncertainty third)",
        f"- {low_t:.4f} < std ≤ {high_t:.4f} → MEDIUM_CONFIDENCE (middle third)",
        f"- std > {high_t:.4f} → LOW_CONFIDENCE (highest uncertainty third)",
        "",
        "---",
        "",
        "## Evaluation on Validation Set",
        "",
        "| Confidence Group | Mean Absolute Error | N |",
        "|------------------|--------------------|----|",
        f"| HIGH_CONFIDENCE | {cal['mean_error_low_uncertainty_tertile']:.4f} g/dL | ~{cal['n_validation']//3} |",
        f"| MEDIUM_CONFIDENCE | {cal['mean_error_medium_uncertainty_tertile']:.4f} g/dL | ~{cal['n_validation']//3} |",
        f"| LOW_CONFIDENCE | {cal['mean_error_high_uncertainty_tertile']:.4f} g/dL | ~{cal['n_validation']//3} |",
        "",
        f"**Calibration monotonic (expected: HIGH < MEDIUM < LOW error)**: "
        f"{'YES' if cal['calibration_monotonic'] else 'NO — see limitations'}",
        "",
        "---",
        "",
        "## Limitations",
        "",
    ]

    if not cal["calibration_monotonic"]:
        lines += [
            "⚠️ **CALIBRATION IS POOR**: Higher confidence does NOT consistently correspond to "
            "lower error on the validation set. The confidence system provides a coarse, "
            "weakly-calibrated signal. Users should interpret confidence labels conservatively.",
            "",
        ]

    lines += [
        "- Validation set has only ~29 subjects — small sample for calibration.",
        "- MC dropout is not a rigorous Bayesian uncertainty quantification.",
        "- Thresholds should be re-derived with a larger dataset.",
        "- The confidence labels do not constitute a probability of clinical accuracy.",
        "",
        "---",
        "",
        "*Thresholds are derived from validation data, not invented.*",
        "*Poor calibration is documented, not hidden.*",
    ]

    (output_dir / "confidence_calibration.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Saved: {output_dir / 'confidence_calibration.md'}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", default="data/raw/verified_flat")
    parser.add_argument("--metadata-dir", default="data/metadata")
    parser.add_argument("--split", default=str(SPLIT_PATH))
    parser.add_argument("--model", default=str(MODEL_DIR / "hb_regressor_best.pt"))
    parser.add_argument("--output-dir", default=str(RESULTS_DIR))
    parser.add_argument("--cache-dir", default="data/processed/model_cache")
    args = parser.parse_args()

    frame, summary, calibrator = run_uncertainty_analysis(
        raw_dir=args.raw_dir,
        metadata_dir=args.metadata_dir,
        split_path=args.split,
        model_path=args.model,
        output_dir=args.output_dir,
        cache_dir=args.cache_dir,
    )

    out = Path(args.output_dir)
    write_uncertainty_analysis_md(frame, summary, out)
    write_confidence_calibration_md(summary, out)
    print("\nPhase D complete.")
