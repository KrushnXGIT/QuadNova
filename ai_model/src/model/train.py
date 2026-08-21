"""Train the Phase 4 Hb regressor using the existing subject-level CV pipeline."""

import argparse
import json
import random
import hashlib
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

from src.data.labels import LabelsUnavailableError, find_metadata_file, load_labels
from src.data.matching import scan_raw_data_dir
from src.data.splitting import assert_no_overlap
from src.data.validate_metadata import MetadataValidationError, validate_metadata
from src.vision.pipeline import process_subject
from .config import *
from .evaluate import mean_baseline_metrics, regression_metrics, save_evaluation_plots
from .model import HbRegressor


def set_seed(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def load_split(path):
    with open(path, encoding="utf-8") as handle:
        payload = json.load(handle)
    split = payload.get("split", payload)
    assert_no_overlap(split)
    return split


def _cache_key(subject_id, raw_path, mask_path):
    payload = f"{subject_id}|{raw_path}|{mask_path}|{INPUT_SIZE}|{NORM_METHOD}|{QUALITY_OVERRIDES}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def build_arrays(raw_dir, split, labels, cache_dir=None):
    records, _ = scan_raw_data_dir(raw_dir)
    labels = labels.set_index("SUBJECT_ID")
    arrays = {}
    rejected = {}
    for split_name, subject_ids in split.items():
        images, targets, ids = [], [], []
        for subject_id in subject_ids:
            if subject_id not in labels.index:
                raise ValueError(f"Missing Hb label for split subject {subject_id}")
            record = records.get(subject_id)
            if record is None or not record.raw_photo or not record.mask_forniceal_palpebral:
                rejected[subject_id] = "missing raw photo or combined ROI mask"
                continue
            raw_path = str(Path(raw_dir) / record.raw_photo)
            mask_path = str(Path(raw_dir) / record.mask_forniceal_palpebral)
            cache_path = None
            if cache_dir:
                cache_path = Path(cache_dir) / f"{_cache_key(subject_id, raw_path, mask_path)}.npz"
            if cache_path and cache_path.is_file():
                cached = np.load(cache_path, allow_pickle=False)
                tensor = cached["roi_tensor"]
            else:
                result = process_subject(
                    subject_id,
                    raw_path,
                    mask_path,
                    norm_method=NORM_METHOD,
                    output_size=INPUT_SIZE,
                    quality_overrides=QUALITY_OVERRIDES,
                )
                if not result.accepted:
                    rejected[subject_id] = result.quality_report["reject_reason"]
                    continue
                tensor = result.roi_tensor.transpose(2, 0, 1)
                if cache_path:
                    cache_path.parent.mkdir(parents=True, exist_ok=True)
                    np.savez_compressed(cache_path, roi_tensor=tensor.astype(np.float32))
            images.append(tensor)
            targets.append(float(labels.loc[subject_id, "Hb"]))
            ids.append(subject_id)
        arrays[split_name] = (np.asarray(images, dtype=np.float32), np.asarray(targets, dtype=np.float32), ids)
    return arrays, rejected


def train(raw_dir, metadata_dir, split_path, model_dir, results_dir, pretrained=False, cache_dir=None, freeze_backbone=False, target_normalize=False):
    set_seed(RANDOM_SEED)
    metadata_path = find_metadata_file(metadata_dir)
    if metadata_path is not None:
        try:
            validate_metadata(metadata_path, raw_dir)
        except MetadataValidationError as error:
            raise SystemExit(f"TRAINING BLOCKED: metadata validation failed: {error}") from error
    try:
        labels = load_labels(metadata_dir)
    except LabelsUnavailableError as error:
        raise SystemExit(f"TRAINING BLOCKED: {error}") from error
    if "Hb" not in labels.columns:
        raise SystemExit("TRAINING BLOCKED: metadata must contain the verified Hb column")
    arrays, rejected = build_arrays(raw_dir, load_split(split_path), labels, cache_dir)
    if any(len(arrays[name][1]) == 0 for name in ("train", "val", "test")):
        raise SystemExit("TRAINING BLOCKED: every split needs at least one accepted labeled subject")

    train_x, train_y, _ = arrays["train"]
    val_x, val_y, _ = arrays["val"]
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = HbRegressor(pretrained=pretrained, freeze_backbone=freeze_backbone).to(device)
    train_mean = float(np.mean(train_y))
    train_std = float(np.std(train_y)) or 1.0
    target_scale = (train_mean, train_std) if target_normalize else (0.0, 1.0)
    train_targets = (train_y - target_scale[0]) / target_scale[1]
    val_targets = (val_y - target_scale[0]) / target_scale[1]
    optimizer = torch.optim.Adam((p for p in model.parameters() if p.requires_grad), lr=LEARNING_RATE)
    loss_fn = nn.MSELoss()
    loader = DataLoader(TensorDataset(torch.from_numpy(train_x), torch.from_numpy(train_targets)), batch_size=BATCH_SIZE, shuffle=True)
    history = {"train_loss": [], "val_loss": []}
    best_val = float("inf")
    patience_count = 0
    model_dir = Path(model_dir)
    model_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = model_dir / "hb_regressor_best.pt"
    for _ in range(MAX_EPOCHS):
        model.train()
        losses = []
        for images, targets in loader:
            optimizer.zero_grad()
            loss = loss_fn(model(images.to(device)), targets.to(device))
            loss.backward()
            optimizer.step()
            losses.append(float(loss.item()))
        model.eval()
        with torch.no_grad():
            val_loss = float(loss_fn(model(torch.from_numpy(val_x).to(device)), torch.from_numpy(val_targets).to(device)).item())
        history["train_loss"].append(float(np.mean(losses)))
        history["val_loss"].append(val_loss)
        if val_loss < best_val:
            best_val = val_loss
            patience_count = 0
            torch.save({"model_state_dict": model.state_dict(), "config": {"input_size": INPUT_SIZE, "norm_method": NORM_METHOD, "model_name": MODEL_NAME, "pretrained": pretrained, "freeze_backbone": freeze_backbone, "target_mean": target_scale[0], "target_std": target_scale[1]}}, checkpoint_path)
        else:
            patience_count += 1
            if patience_count >= PATIENCE:
                break

    model.load_state_dict(torch.load(checkpoint_path, map_location=device, weights_only=False)["model_state_dict"])
    metrics = {}
    predictions = {}
    for name, (images, targets, _) in arrays.items():
        with torch.no_grad():
            predictions[name] = model(torch.from_numpy(images).to(device)).cpu().numpy() * target_scale[1] + target_scale[0]
        metrics[name] = regression_metrics(targets, predictions[name])
    metrics["test_baseline"] = mean_baseline_metrics(train_y, arrays["test"][1])
    results_dir = Path(results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)
    save_evaluation_plots(history, arrays["test"][1], predictions["test"], results_dir)
    with open(results_dir / "metrics.json", "w", encoding="utf-8") as handle:
        json.dump({"metrics": metrics, "rejected": rejected, "device": str(device), "history": history}, handle, indent=2)
    return metrics, checkpoint_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", default="data/raw")
    parser.add_argument("--metadata-dir", default="data/metadata")
    parser.add_argument("--split", default=str(SPLIT_PATH))
    parser.add_argument("--model-dir", default=str(MODEL_DIR))
    parser.add_argument("--results-dir", default=str(RESULTS_DIR))
    parser.add_argument("--pretrained", action="store_true")
    parser.add_argument("--cache-dir", default="data/processed/model_cache")
    parser.add_argument("--freeze-backbone", action="store_true")
    parser.add_argument("--target-normalize", action="store_true")
    args = parser.parse_args()
    metrics, checkpoint = train(args.raw_dir, args.metadata_dir, args.split, args.model_dir, args.results_dir, args.pretrained, args.cache_dir, args.freeze_backbone, args.target_normalize)
    print(json.dumps({"metrics": metrics, "checkpoint": str(checkpoint)}, indent=2))


if __name__ == "__main__":
    main()
