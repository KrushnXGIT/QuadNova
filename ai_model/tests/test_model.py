"""Focused Phase 4 model and training-guard tests."""

import json

import numpy as np
import pytest
import torch
from PIL import Image

from src.data.splitting import assert_no_overlap
from src.model.evaluate import regression_metrics
from src.model.model import HbRegressor
from src.model.predict import predict, predict_with_confidence
from src.model.train import train


def test_regressor_returns_one_value_per_image():
    model = HbRegressor(pretrained=False).eval()
    with torch.no_grad():
        output = model(torch.zeros(2, 3, 224, 224))
    assert tuple(output.shape) == (2,)


def test_regression_metrics_are_calculated():
    metrics = regression_metrics([1.0, 2.0, 3.0], [1.0, 2.0, 4.0])
    assert metrics["MAE"] == pytest.approx(1 / 3)
    assert metrics["RMSE"] == pytest.approx((1 / 3) ** 0.5)
    assert metrics["R2"] == pytest.approx(0.5)


def test_subject_overlap_is_rejected():
    with pytest.raises(AssertionError, match="Subject leakage"):
        assert_no_overlap({"train": ["a"], "val": ["a"], "test": ["b"]})


def test_saved_model_can_be_reloaded(tmp_path):
    model = HbRegressor(pretrained=False).eval()
    checkpoint = tmp_path / "model.pt"
    torch.save({"model_state_dict": model.state_dict()}, checkpoint)
    loaded = HbRegressor(pretrained=False).eval()
    loaded.load_state_dict(torch.load(checkpoint, map_location="cpu", weights_only=False)["model_state_dict"])
    with torch.no_grad():
        assert torch.equal(model(torch.zeros(1, 3, 224, 224)), loaded(torch.zeros(1, 3, 224, 224)))


def test_training_blocks_without_labels(tmp_path):
    split_path = tmp_path / "split.json"
    split_path.write_text(json.dumps({"split": {"train": ["a"], "val": ["b"], "test": ["c"]}}), encoding="utf-8")
    with pytest.raises(SystemExit, match="TRAINING BLOCKED"):
        train("data/raw/sample_dataset", "data/metadata", split_path, tmp_path / "models", tmp_path / "results")


def test_predict_with_confidence_returns_uncertainty(tmp_path):
    raw = np.random.default_rng(0).integers(0, 255, size=(224, 224, 3), dtype=np.uint8)
    Image.fromarray(raw, mode="RGB").save(tmp_path / "sample.jpg")

    mask = np.zeros((224, 224, 4), dtype=np.uint8)
    yy, xx = np.ogrid[:224, :224]
    circle = (yy - 112) ** 2 + (xx - 112) ** 2 <= 80 ** 2
    mask[circle] = [40, 80, 120, 255]
    Image.fromarray(mask, mode="RGBA").save(tmp_path / "sample_mask.png")

    checkpoint = tmp_path / "confidence_model.pt"
    model = HbRegressor(pretrained=False).eval()
    torch.save({"model_state_dict": model.state_dict(), "config": {"target_mean": 12.0, "target_std": 1.5}}, checkpoint)

    result = predict_with_confidence(str(tmp_path / "sample.jpg"), str(tmp_path / "sample_mask.png"), str(checkpoint), "synthetic", mc_samples=3)
    assert result["image_quality_status"] == "ACCEPTED"
    assert result["estimated_hb_g_dl"] is not None
    assert result["estimated_hb_g_dl"] >= 0
    assert result["hb_std_g_dl"] is not None
    assert result["hb_std_g_dl"] >= 0
    assert result["confidence_interval_95"] is not None
    assert len(result["confidence_interval_95"]) == 2
    # Verify full output schema
    assert "confidence_status" in result
    assert "recommendation" in result
    assert "model_version" in result
    assert "_disclaimer" in result
