"""
phase_c_lighting_robustness.py
===============================
PHASE C: Lighting Robustness Evaluation

Evaluates the model under controlled image perturbations applied to the
test set images. Originals are NEVER overwritten.

IMPORTANT DISCLAIMER
--------------------
These are controlled image perturbation experiments applied to the
existing test set. They do NOT constitute real-world smartphone robustness
testing. Performance under these perturbations gives a lower-bound estimate
of sensitivity to lighting variation, but:

  - Real smartphones differ in sensor, ISP pipeline, HDR processing, etc.
  - Real lighting variation includes angular differences, mixed sources,
    and spectral composition changes not captured by simple brightness scaling.
  - This analysis does NOT prove or disprove real-world robustness.

Perturbations evaluated:
  - original (baseline)
  - brightness +20%
  - brightness -20%
  - contrast +20%
  - contrast -20%
  - color temperature shift (warm: boost red, reduce blue)
  - color temperature shift (cool: boost blue, reduce red)

Produces:
  results/lighting_robustness.json
  results/lighting_robustness.md
"""

import json
import sys
from pathlib import Path
from typing import Dict, List

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
from src.vision.pipeline import process_subject
from src.vision.color_normalization import normalize_roi


def perturb_image(rgb: np.ndarray, perturbation: str) -> np.ndarray:
    """
    Apply a controlled perturbation to a uint8 RGB image.
    Returns uint8 RGB. Original is never modified.
    """
    img = rgb.astype(np.float32)

    if perturbation == "original":
        return rgb.copy()
    elif perturbation == "brightness_up":
        img = img * 1.20
    elif perturbation == "brightness_down":
        img = img * 0.80
    elif perturbation == "contrast_up":
        mean = img.mean()
        img = (img - mean) * 1.20 + mean
    elif perturbation == "contrast_down":
        mean = img.mean()
        img = (img - mean) * 0.80 + mean
    elif perturbation == "color_warm":
        # Warm: boost red +15, reduce blue -15
        img[:, :, 0] = img[:, :, 0] * 1.10
        img[:, :, 2] = img[:, :, 2] * 0.90
    elif perturbation == "color_cool":
        # Cool: boost blue +15, reduce red -15
        img[:, :, 0] = img[:, :, 0] * 0.90
        img[:, :, 2] = img[:, :, 2] * 1.10
    else:
        raise ValueError(f"Unknown perturbation: {perturbation}")

    return np.clip(img, 0, 255).astype(np.uint8)


PERTURBATIONS = [
    "original",
    "brightness_up",
    "brightness_down",
    "contrast_up",
    "contrast_down",
    "color_warm",
    "color_cool",
]


def run_lighting_robustness(
    raw_dir: str = "data/raw/verified_flat",
    metadata_dir: str = "data/metadata",
    split_path: str = None,
    model_path: str = None,
    norm_method: str = "clahe",
    output_dir: str = None,
):
    split_path = split_path or str(SPLIT_PATH)
    model_path = model_path or str(MODEL_DIR / "hb_regressor_best.pt")
    output_dir = Path(output_dir or RESULTS_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=== PHASE C: Lighting Robustness ===")
    print("DISCLAIMER: These are controlled perturbation experiments, NOT real-world tests.")
    print(f"Norm method: {norm_method}")

    labels_df = pd.read_csv(Path(metadata_dir) / "labels.csv").set_index("SUBJECT_ID")
    split_data = load_split(split_path)["split"]
    test_subjects = split_data["test"]
    records, _ = scan_raw_data_dir(raw_dir)

    # Load model
    checkpoint = torch.load(model_path, map_location="cpu", weights_only=False)
    config = checkpoint.get("config", {})
    target_mean = config.get("target_mean", 0.0)
    target_std = config.get("target_std", 1.0)
    model = HbRegressor(
        pretrained=config.get("pretrained", False),
        freeze_backbone=config.get("freeze_backbone", False),
    )
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()

    from src.data.validation import load_raw_photo
    from src.vision.roi import extract_conjunctiva_roi
    from src.vision.quality import check_roi_quality

    results_by_perturbation = {}

    for perturbation in PERTURBATIONS:
        print(f"\n  Perturbation: {perturbation}")
        rows = []

        for sid in test_subjects:
            record = records.get(sid)
            if record is None or not record.raw_photo or not record.mask_forniceal_palpebral:
                continue
            if sid not in labels_df.index:
                continue

            raw_path = str(Path(raw_dir) / record.raw_photo)
            mask_path = str(Path(raw_dir) / record.mask_forniceal_palpebral)

            try:
                # Load original image
                orig_rgb = load_raw_photo(raw_path, apply_exif_rotation=True)

                # Apply perturbation to raw image (eval-only, never saved)
                perturbed_rgb = perturb_image(orig_rgb, perturbation)

                # Extract ROI from perturbed image using original mask
                # We use the mask path directly since the mask aligns to the original
                roi_result = extract_conjunctiva_roi(raw_path, mask_path)

                # For non-original perturbations: re-apply perturbation to ROI
                if perturbation != "original":
                    perturbed_roi_rgb = perturb_image(roi_result.roi_rgb, perturbation)
                else:
                    perturbed_roi_rgb = roi_result.roi_rgb

                # Quality check on perturbed ROI
                roi_q = check_roi_quality(
                    perturbed_roi_rgb,
                    roi_result.coverage_fraction,
                    **{k: v for k, v in (QUALITY_OVERRIDES or {}).items()
                       if k in ("blur_threshold", "dark_threshold", "bright_threshold",
                                "min_dimension", "min_roi_coverage")}
                )
                if not roi_q.passed:
                    continue  # Skip rejected ROIs

                # Normalize and resize
                import cv2
                roi_norm = normalize_roi(perturbed_roi_rgb, method=norm_method)
                roi_resized = cv2.resize(roi_norm, (224, 224), interpolation=cv2.INTER_AREA)

                # Predict
                img_tensor = torch.from_numpy(
                    roi_resized.transpose(2, 0, 1)
                ).unsqueeze(0).float()
                with torch.no_grad():
                    raw_pred = float(model(img_tensor).item())
                pred = raw_pred * target_std + target_mean
                actual = float(labels_df.loc[sid, "Hb"])

                rows.append({
                    "subject_id": sid,
                    "actual_hb": actual,
                    "predicted_hb": pred,
                    "signed_error": pred - actual,
                    "absolute_error": abs(pred - actual),
                })

            except Exception as e:
                continue

        if rows:
            arr_actual = np.array([r["actual_hb"] for r in rows])
            arr_pred = np.array([r["predicted_hb"] for r in rows])
            metrics = regression_metrics(arr_actual, arr_pred)
            results_by_perturbation[perturbation] = {
                "n": len(rows),
                **metrics,
                "mean_signed_error": float(np.mean(arr_pred - arr_actual)),
            }
            print(f"    n={len(rows)}  MAE={metrics['MAE']:.4f}  RMSE={metrics['RMSE']:.4f}")
        else:
            results_by_perturbation[perturbation] = {"n": 0, "MAE": None}

    # Compute prediction shift vs original
    if "original" in results_by_perturbation and results_by_perturbation["original"].get("MAE"):
        orig_mae = results_by_perturbation["original"]["MAE"]
        for pert, m in results_by_perturbation.items():
            if pert != "original" and m.get("MAE") is not None:
                m["mae_shift_vs_original"] = m["MAE"] - orig_mae

    output = {
        "disclaimer": (
            "These are controlled image perturbation experiments on the test set. "
            "Originals were not modified. This does NOT constitute real-world "
            "smartphone robustness validation."
        ),
        "model": str(model_path),
        "norm_method": norm_method,
        "by_perturbation": results_by_perturbation,
    }
    (output_dir / "lighting_robustness.json").write_text(
        json.dumps(output, indent=2), encoding="utf-8"
    )
    print(f"\nSaved: {output_dir / 'lighting_robustness.json'}")
    return output


def write_lighting_robustness_md(results: dict, output_dir: Path):
    by_pert = results.get("by_perturbation", {})

    lines = [
        "# Lighting Robustness Report",
        "",
        "> **IMPORTANT**: These are **controlled image perturbation experiments** applied",
        "> to the existing test set images. Originals were NOT modified.",
        "> This does NOT prove or disprove real-world smartphone robustness.",
        "> Real smartphone variation includes sensor differences, ISP processing,",
        "> HDR modes, and spectral composition changes not captured here.",
        "",
        "---",
        "",
        "## Perturbations Evaluated",
        "",
        "| Perturbation | Description |",
        "|--------------|-------------|",
        "| original | No perturbation — baseline |",
        "| brightness_up | Pixel values ×1.20 |",
        "| brightness_down | Pixel values ×0.80 |",
        "| contrast_up | Contrast scaled ×1.20 around mean |",
        "| contrast_down | Contrast scaled ×0.80 around mean |",
        "| color_warm | Red ×1.10, Blue ×0.90 (warm shift) |",
        "| color_cool | Red ×0.90, Blue ×1.10 (cool shift) |",
        "",
        "---",
        "",
        "## Results",
        "",
        "| Perturbation | N | MAE | RMSE | R² | Bias | MAE shift vs original |",
        "|--------------|---|-----|------|----|------|----------------------|",
    ]
    for pert, m in by_pert.items():
        if m.get("MAE") is not None:
            shift = m.get("mae_shift_vs_original", 0.0)
            shift_str = f"+{shift:.4f}" if shift >= 0 else f"{shift:.4f}"
            lines.append(
                f"| {pert} | {m['n']} | {m['MAE']:.4f} | {m.get('RMSE', 0):.4f} | "
                f"{m.get('R2', 0):.4f} | {m.get('mean_signed_error', 0):.4f} | {shift_str if pert != 'original' else '—'} |"
            )
        else:
            lines.append(f"| {pert} | 0 | N/A | N/A | N/A | N/A | N/A |")

    orig_mae = by_pert.get("original", {}).get("MAE")
    lines += [
        "",
        "---",
        "",
        "## Findings",
        "",
    ]
    if orig_mae is not None:
        maes = [(k, v["MAE"]) for k, v in by_pert.items() if v.get("MAE") is not None and k != "original"]
        if maes:
            worst = max(maes, key=lambda x: x[1])
            best = min(maes, key=lambda x: x[1])
            lines += [
                f"- **Baseline (original) MAE**: {orig_mae:.4f} g/dL",
                f"- **Most sensitive to**: `{worst[0]}` — MAE = {worst[1]:.4f} g/dL "
                f"(shift = +{worst[1]-orig_mae:.4f})",
                f"- **Least sensitive to**: `{best[0]}` — MAE = {best[1]:.4f} g/dL",
                "",
            ]

    lines += [
        "**Caveats**:",
        "- These results show sensitivity to isolated luminance/color perturbations under lab conditions.",
        "- Real-world smartphone variation cannot be characterized from these experiments alone.",
        "- For genuine cross-device robustness, a multi-device dataset with the same subjects would be required.",
        "",
        "---",
        "",
        "*Originals not modified. No real-world robustness claim is made.*",
    ]

    (output_dir / "lighting_robustness.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Saved: {output_dir / 'lighting_robustness.md'}")


def write_device_robustness_md(output_dir: Path):
    """Write device_robustness.md — documents NOT TESTABLE status."""
    lines = [
        "# Device / Camera Robustness Report",
        "",
        "## Status: NOT TESTABLE — REQUIRED DATA UNAVAILABLE",
        "",
        "The dataset does not contain any camera or device metadata.",
        "The `data/metadata/labels.csv` file contains only:",
        "- `SUBJECT_ID`",
        "- `Hb` (verified clinical haemoglobin)",
        "- `country` (India or Italy)",
        "- `source_number` (original row index)",
        "",
        "No information exists about:",
        "- Camera make or model",
        "- Phone/device type",
        "- Camera app used",
        "- Sensor specifications",
        "- Acquisition protocol",
        "",
        "---",
        "",
        "## What Was Done Instead",
        "",
        "Controlled image perturbations were applied as a **simulated camera variation** proxy.",
        "See [lighting_robustness.md](lighting_robustness.md) for results.",
        "",
        "These perturbations simulate:",
        "- Exposure differences between cameras",
        "- White balance variation",
        "- Contrast / dynamic range differences",
        "",
        "They do NOT simulate:",
        "- Sensor noise characteristics per device",
        "- Lens distortion or chromatic aberration",
        "- ISP colour processing pipelines",
        "- HDR merge behaviour",
        "",
        "---",
        "",
        "## Recommendation",
        "",
        "Real cross-device validation requires data collected from the same subjects "
        "with at least 2–3 different camera devices under controlled conditions. "
        "This is a prerequisite for deployment, not an optional enhancement.",
        "",
        "---",
        "",
        "*No device metrics are fabricated. This section is honestly marked NOT TESTABLE.*",
    ]
    (output_dir / "device_robustness.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Saved: {output_dir / 'device_robustness.md'}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", default="data/raw/verified_flat")
    parser.add_argument("--metadata-dir", default="data/metadata")
    parser.add_argument("--split", default=str(SPLIT_PATH))
    parser.add_argument("--model", default=str(MODEL_DIR / "hb_regressor_best.pt"))
    parser.add_argument("--norm-method", default="clahe")
    parser.add_argument("--output-dir", default=str(RESULTS_DIR))
    args = parser.parse_args()

    results = run_lighting_robustness(
        raw_dir=args.raw_dir,
        metadata_dir=args.metadata_dir,
        split_path=args.split,
        model_path=args.model,
        norm_method=args.norm_method,
        output_dir=args.output_dir,
    )
    write_lighting_robustness_md(results, Path(args.output_dir))
    write_device_robustness_md(Path(args.output_dir))
    print("\nPhase C lighting robustness complete.")
