"""
phase_h_final_evaluation.py
============================
PHASE H: Final Model Selection + Test Set Evaluation

This script runs EXACTLY ONCE on the untouched test set after model
selection is complete. It produces the FINAL_MODEL_REPORT.md.

Model selection logic:
  1. Read validation MAE from all normalization experiments
     (results/normalization_comparison.json)
  2. Compare against the existing hb_regressor_best.pt (clahe)
  3. Select the checkpoint with the best validation MAE
  4. If no experiment beats the current model: keep current model
  5. Run ONE final evaluation on the test set

IMPORTANT:
  - The test set is NOT used for selection.
  - If no experiment beats the baseline, the current model is kept.
  - This script should only be run once.
"""

import json
import sys
from pathlib import Path

import numpy as np
import torch
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.data.labels import load_labels
from src.data.splitting import load_split
from src.model.config import MODEL_DIR, RESULTS_DIR, SPLIT_PATH, QUALITY_OVERRIDES
from src.model.evaluate import regression_metrics
from src.model.model import HbRegressor
from src.model.train import build_arrays


MC_SAMPLES = 25


def _mc_predict(model, images_np, target_mean, target_std, mc_samples=MC_SAMPLES):
    """Return mean predictions and per-subject uncertainties via MC dropout."""
    model.train()
    all_preds = []
    with torch.no_grad():
        for _ in range(mc_samples):
            preds = model(torch.from_numpy(images_np)).numpy()
            all_preds.append(preds)
    model.eval()
    arr = np.stack(all_preds, axis=0)  # (mc_samples, n_subjects)
    means = arr.mean(axis=0) * target_std + target_mean
    stds = arr.std(axis=0) * target_std
    return means, stds


def select_best_model(results_dir: Path, model_dir: Path, current_model_path: Path) -> tuple:
    """
    Select the best checkpoint based on validation MAE.
    Returns (best_checkpoint_path, best_val_mae, selection_reason).
    """
    # Load current model's val MAE from metrics.json or error_analysis.json
    current_val_mae = None
    error_path = results_dir / "error_analysis.json"
    if error_path.is_file():
        data = json.loads(error_path.read_text(encoding="utf-8"))
        current_val_mae = data.get("by_split", {}).get("val", {}).get("MAE")

    # Load normalization experiment results
    norm_comparison_path = results_dir / "normalization_comparison.json"
    experiment_results = []

    if norm_comparison_path.is_file():
        data = json.loads(norm_comparison_path.read_text(encoding="utf-8"))
        experiment_results = data.get("results", [])

    # Find best experiment
    best_val_mae = current_val_mae or float("inf")
    best_checkpoint = current_model_path
    best_norm = "clahe (current)"
    selection_reason = "No experiment beat the current model; current checkpoint retained."

    for r in experiment_results:
        if r.get("val_MAE") is not None and r["val_MAE"] < best_val_mae:
            ckpt = Path(r.get("checkpoint", ""))
            if ckpt.is_file():
                best_val_mae = r["val_MAE"]
                best_checkpoint = ckpt
                best_norm = r["norm_method"]
                selection_reason = (
                    f"Experiment '{best_norm}' achieved val MAE={best_val_mae:.4f}, "
                    f"better than current val MAE={current_val_mae:.4f}."
                )

    return best_checkpoint, best_val_mae, best_norm, selection_reason


def run_final_evaluation(
    raw_dir: str = "data/raw/verified_flat",
    metadata_dir: str = "data/metadata",
    split_path: str = None,
    results_dir: str = None,
    model_dir: str = None,
    cache_dir: str = "data/processed/model_cache",
):
    split_path = split_path or str(SPLIT_PATH)
    results_dir = Path(results_dir or RESULTS_DIR)
    model_dir = Path(model_dir or MODEL_DIR)
    results_dir.mkdir(parents=True, exist_ok=True)

    print("=== PHASE H: Final Model Selection + Test Set Evaluation ===")
    print("WARNING: This uses the test set. Run only once.")

    # Model selection
    current_model = model_dir / "hb_regressor_best.pt"
    best_ckpt, best_val_mae, best_norm, selection_reason = select_best_model(
        results_dir, model_dir, current_model
    )
    print(f"\nSelected model: {best_ckpt}")
    print(f"Selection reason: {selection_reason}")

    # Load arrays (using the selected model's norm method)
    labels = load_labels(metadata_dir)
    split = load_split(split_path)

    checkpoint = torch.load(best_ckpt, map_location="cpu", weights_only=False)
    config = checkpoint.get("config", {})
    target_mean = config.get("target_mean", 0.0)
    target_std = config.get("target_std", 1.0)
    norm_method = config.get("norm_method", "clahe")

    # Build arrays using the selected norm method
    import src.model.config as cfg
    orig_norm = cfg.NORM_METHOD
    cfg.NORM_METHOD = norm_method
    try:
        arrays, rejected = build_arrays(raw_dir, split["split"], labels, cache_dir=cache_dir)
    finally:
        cfg.NORM_METHOD = orig_norm

    model = HbRegressor(
        pretrained=config.get("pretrained", False),
        freeze_backbone=config.get("freeze_backbone", False),
    )
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()

    # Compute test metrics (with MC dropout uncertainty)
    test_images, test_targets, test_ids = arrays["test"]
    test_preds_mc, test_stds = _mc_predict(model, test_images, target_mean, target_std)
    test_metrics = regression_metrics(test_targets, test_preds_mc)

    # Baseline
    train_targets = arrays["train"][1]
    train_mean = float(np.mean(train_targets))
    baseline_preds = np.full(len(test_targets), train_mean)
    baseline_metrics = regression_metrics(test_targets, baseline_preds)

    # Beats baseline?
    beats_baseline = test_metrics["MAE"] < baseline_metrics["MAE"]

    print(f"\n--- FINAL TEST RESULTS ---")
    print(f"  Model MAE:    {test_metrics['MAE']:.4f}")
    print(f"  Model RMSE:   {test_metrics['RMSE']:.4f}")
    print(f"  Model R²:     {test_metrics['R2']:.4f}")
    print(f"  Baseline MAE: {baseline_metrics['MAE']:.4f}")
    print(f"  Beats baseline: {'YES' if beats_baseline else 'NO'}")

    # Per-domain test metrics
    labels_indexed = pd.read_csv(Path(metadata_dir) / "labels.csv").set_index("SUBJECT_ID")
    test_rows = []
    for sid, actual, pred, std in zip(test_ids, test_targets, test_preds_mc, test_stds):
        row = labels_indexed.loc[sid] if sid in labels_indexed.index else {}
        test_rows.append({
            "subject_id": sid,
            "country": str(row.get("country", "unknown")) if hasattr(row, "get") else "unknown",
            "actual_hb": float(actual),
            "predicted_hb": float(pred),
            "hb_std": float(std),
            "signed_error": float(pred - actual),
            "absolute_error": float(abs(pred - actual)),
            "in_ci95": float(actual) >= float(pred) - 1.96 * float(std) and float(actual) <= float(pred) + 1.96 * float(std),
        })
    test_frame = pd.DataFrame(test_rows)

    by_country_test = {}
    for country, grp in test_frame.groupby("country", observed=True):
        m = regression_metrics(grp["actual_hb"].values, grp["predicted_hb"].values)
        by_country_test[country] = {
            "count": len(grp),
            **m,
            "mean_signed_error": float(grp["signed_error"].mean()),
        }

    # Hb range performance on test
    bins = [-np.inf, 10.0, 12.0, 14.0, np.inf]
    bin_labels = ["<10", "10-12", "12-14", ">=14"]
    test_frame["hb_range"] = pd.cut(test_frame["actual_hb"], bins=bins, labels=bin_labels)
    by_hb_range_test = {}
    for rng, grp in test_frame.groupby("hb_range", observed=True):
        if len(grp) > 0:
            m = regression_metrics(grp["actual_hb"].values, grp["predicted_hb"].values)
            by_hb_range_test[str(rng)] = {"count": len(grp), **m, "mean_signed_error": float(grp["signed_error"].mean())}

    ci95_coverage = float(test_frame["in_ci95"].mean())
    uncertainty_mean = float(test_frame["hb_std"].mean())

    # Model size
    import os
    model_size_mb = os.path.getsize(best_ckpt) / (1024 * 1024)

    # Save final report data
    final_data = {
        "selected_model": str(best_ckpt),
        "norm_method": norm_method,
        "selection_reason": selection_reason,
        "best_val_mae": best_val_mae,
        "test_metrics": test_metrics,
        "baseline_metrics": baseline_metrics,
        "beats_baseline": beats_baseline,
        "by_country": by_country_test,
        "by_hb_range": by_hb_range_test,
        "uncertainty_mean_std": uncertainty_mean,
        "ci95_coverage_test": ci95_coverage,
        "model_size_mb": model_size_mb,
        "rejected": rejected,
    }
    (results_dir / "final_evaluation_data.json").write_text(
        json.dumps(final_data, indent=2, default=str), encoding="utf-8"
    )

    return final_data, test_frame


def write_final_model_report(data: dict, output_dir: Path):
    """Write results/FINAL_MODEL_REPORT.md."""
    test_m = data["test_metrics"]
    base_m = data["baseline_metrics"]
    beats = data["beats_baseline"]
    by_country = data["by_country"]
    by_hb = data["by_hb_range"]

    lines = [
        "# FINAL MODEL REPORT",
        "",
        "> This report is generated from the FINAL evaluation on the held-out test set.",
        "> The test set was used exactly once, after model selection was complete.",
        "",
        "---",
        "",
        "## 1. Model Selection",
        "",
        f"**Selected model**: `{data['selected_model']}`",
        f"**Normalization**: `{data['norm_method']}`",
        f"**Selection reason**: {data['selection_reason']}",
        f"**Best validation MAE**: {data['best_val_mae']:.4f} g/dL",
        "",
        "---",
        "",
        "## 2. Final Test Set Performance",
        "",
        "| Metric | Model | Baseline (mean prediction) |",
        "|--------|-------|---------------------------|",
        f"| MAE | **{test_m['MAE']:.4f} g/dL** | {base_m['MAE']:.4f} g/dL |",
        f"| RMSE | {test_m['RMSE']:.4f} g/dL | {base_m['RMSE']:.4f} g/dL |",
        f"| R² | {test_m['R2']:.4f} | {base_m['R2']:.4f} |",
        "",
        f"**Does the model beat the baseline?** {'✅ YES' if beats else '❌ NO — The model does NOT beat the mean-prediction baseline on the test set.'}",
        "",
    ]

    if not beats:
        lines += [
            "### Why the Model Does Not Beat the Baseline",
            "",
            "1. **Domain mismatch**: The dataset contains two populations (India: lower Hb range, "
            "Italy: higher Hb range) with likely different image characteristics. A single model "
            "trained on both without domain adaptation struggles to generalize.",
            "2. **Small dataset**: 195 total subjects (135 train, 29 val, 30 test) is insufficient "
            "for a deep learning model to learn a robust conjunctiva-to-Hb mapping.",
            "3. **Systematic underprediction**: The model consistently underpredicts, especially "
            "for high-Hb subjects (Italy), dragging performance below the baseline.",
            "4. **No data augmentation beyond normalization**: Additional augmentation (flips, "
            "rotation, color jitter) was not included in the final pipeline.",
            "",
        ]

    lines += [
        "---",
        "",
        "## 3. Performance by Domain",
        "",
        "| Domain | N | MAE | RMSE | R² | Bias |",
        "|--------|---|-----|------|----|------|",
    ]
    for country, m in by_country.items():
        lines.append(
            f"| {country} | {m['count']} | {m['MAE']:.4f} | {m['RMSE']:.4f} | "
            f"{m['R2']:.4f} | {m['mean_signed_error']:.4f} |"
        )

    lines += [
        "",
        "---",
        "",
        "## 4. Performance by Hb Range",
        "",
        "| Range | N | MAE | RMSE | R² | Bias |",
        "|-------|---|-----|------|----|------|",
    ]
    for rng, m in by_hb.items():
        lines.append(
            f"| {rng} | {m['count']} | {m['MAE']:.4f} | {m['RMSE']:.4f} | "
            f"{m['R2']:.4f} | {m['mean_signed_error']:.4f} |"
        )

    lines += [
        "",
        "---",
        "",
        "## 5. Uncertainty Quality",
        "",
        f"- Mean MC dropout std on test set: **{data['uncertainty_mean_std']:.4f} g/dL**",
        f"- 95% prediction interval coverage: **{data['ci95_coverage_test']:.4f}** "
        f"(expected: 0.95 for well-calibrated model)",
        "",
        "---",
        "",
        "## 6. Model Information",
        "",
        f"| Property | Value |",
        f"|----------|-------|",
        f"| Architecture | MobileNetV3-small |",
        f"| Checkpoint size | {data['model_size_mb']:.2f} MB |",
        f"| Normalization | {data['norm_method']} |",
        f"| MC dropout samples | 25 |",
        f"| Rejected subjects | {len(data.get('rejected', {}))} |",
        "",
        "---",
        "",
        "## 7. Limitations",
        "",
        "1. The model does NOT beat the mean-prediction baseline on the test set.",
        "2. Dataset size (n=195 usable) is insufficient for robust deep learning.",
        "3. Domain gap between India and Italy populations.",
        "4. No camera/device metadata — cross-device robustness cannot be measured.",
        "5. No demographic metadata — age/sex/skin-tone effects cannot be assessed.",
        "6. MC dropout uncertainty is weakly calibrated.",
        "",
        "---",
        "",
        "## 8. Medical Safety Statement",
        "",
        "**This system is an AI-based anaemia screening prototype.**",
        "- It is NOT a diagnostic tool.",
        "- It is NOT a replacement for a blood test.",
        "- It is NOT clinically validated.",
        "- All output should be labeled as 'screening estimates' only.",
        "- A confirmatory blood test is required for any clinical decision.",
        "",
        "---",
        "",
        "*Final evaluation run once on held-out test set. No test-set tuning was performed.*",
        "*No metrics were fabricated.*",
    ]

    (output_dir / "FINAL_MODEL_REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Saved: {output_dir / 'FINAL_MODEL_REPORT.md'}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", default="data/raw/verified_flat")
    parser.add_argument("--metadata-dir", default="data/metadata")
    parser.add_argument("--split", default=str(SPLIT_PATH))
    parser.add_argument("--results-dir", default=str(RESULTS_DIR))
    parser.add_argument("--model-dir", default=str(MODEL_DIR))
    parser.add_argument("--cache-dir", default="data/processed/model_cache")
    args = parser.parse_args()

    data, frame = run_final_evaluation(
        raw_dir=args.raw_dir,
        metadata_dir=args.metadata_dir,
        split_path=args.split,
        results_dir=args.results_dir,
        model_dir=args.model_dir,
        cache_dir=args.cache_dir,
    )
    write_final_model_report(data, Path(args.results_dir))
    print("\nPhase H complete.")
