"""Generate subgroup and residual analysis for a saved Hb model."""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import torch

from src.data.splitting import load_split
from .config import MODEL_DIR, RESULTS_DIR, SPLIT_PATH
from .evaluate import regression_metrics
from .model import HbRegressor
from .train import build_arrays


def _metrics(frame):
    if len(frame) == 0:
        return {"count": 0}
    values = regression_metrics(frame["actual_hb"].to_numpy(), frame["predicted_hb"].to_numpy())
    return {"count": len(frame), **values}


def analyze(raw_dir, metadata_dir, split_path, model_path, output_dir, cache_dir="data/processed/model_cache"):
    labels = pd.read_csv(Path(metadata_dir) / "labels.csv").set_index("SUBJECT_ID")
    split = load_split(split_path)["split"]
    arrays, rejected = build_arrays(raw_dir, split, labels.reset_index(), cache_dir)
    checkpoint = torch.load(model_path, map_location="cpu", weights_only=False)
    config = checkpoint.get("config", {})
    model = HbRegressor(
        pretrained=config.get("pretrained", False),
        freeze_backbone=config.get("freeze_backbone", False),
    )
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()
    target_mean = config.get("target_mean", 0.0)
    target_std = config.get("target_std", 1.0)

    rows = []
    for split_name, (images, targets, subject_ids) in arrays.items():
        with torch.no_grad():
            predictions = model(torch.from_numpy(images)).numpy() * target_std + target_mean
        for subject_id, actual, predicted in zip(subject_ids, targets, predictions):
            label = labels.loc[subject_id]
            rows.append({
                "subject_id": subject_id,
                "split": split_name,
                "country": label.get("country", "unknown"),
                "actual_hb": float(actual),
                "predicted_hb": float(predicted),
                "error": float(predicted - actual),
                "absolute_error": float(abs(predicted - actual)),
            })
    frame = pd.DataFrame(rows)
    frame["hb_range"] = pd.cut(frame["actual_hb"], bins=[-np.inf, 10, 12, 14, np.inf], labels=["<10", "10-12", "12-14", ">=14"])
    report = {
        "model": str(model_path),
        "rejected": rejected,
        "overall": _metrics(frame),
        "by_split": {name: _metrics(group) for name, group in frame.groupby("split", observed=True)},
        "by_country": {name: _metrics(group) for name, group in frame.groupby("country", observed=True)},
        "by_hb_range": {str(name): _metrics(group) for name, group in frame.groupby("hb_range", observed=True)},
        "largest_absolute_errors": frame.nlargest(10, "absolute_error").to_dict(orient="records"),
    }
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output_dir / "error_analysis_samples.csv", index=False)
    (output_dir / "error_analysis.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", default="data/raw/verified_flat")
    parser.add_argument("--metadata-dir", default="data/metadata")
    parser.add_argument("--split", default=str(SPLIT_PATH))
    parser.add_argument("--model", default=str(MODEL_DIR / "hb_regressor_best.pt"))
    parser.add_argument("--output-dir", default=str(RESULTS_DIR))
    parser.add_argument("--cache-dir", default="data/processed/model_cache")
    args = parser.parse_args()
    print(json.dumps(analyze(args.raw_dir, args.metadata_dir, args.split, args.model, args.output_dir, args.cache_dir), indent=2, default=str))


if __name__ == "__main__":
    main()
