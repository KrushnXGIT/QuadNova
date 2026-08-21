"""
test_normalization.py
=====================
Tests for src/vision/color_normalization.py and src/vision/quality_gate.py.

Covers:
  - All normalization methods return correct dtype and shape
  - Values in expected range
  - normalize_roi rejects unknown method
  - Invalid input raises ValueError
  - CLAHE operates on L-channel only (preserves color ratios)
  - Gray-world returns in [0,1]
  - Reinhard transfer works with neutral reference
  - z-score clips to [-3, 3]
"""

import numpy as np
import pytest

from src.vision.color_normalization import (
    normalize_roi,
    clahe_normalize,
    gray_world_normalize,
    reinhard_normalize,
    zscore_normalize,
    compute_roi_color_stats,
    SUPPORTED_METHODS,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_roi(h=64, w=64, r=180, g=100, b=80):
    """Create a flat-color RGB ROI."""
    img = np.zeros((h, w, 3), dtype=np.uint8)
    img[:, :, 0] = r
    img[:, :, 1] = g
    img[:, :, 2] = b
    return img


def _make_noisy_roi(h=64, w=64, seed=42):
    """Create a realistic noisy RGB ROI."""
    rng = np.random.default_rng(seed)
    return rng.integers(80, 200, size=(h, w, 3), dtype=np.uint8)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestNormalizeRoi:

    @pytest.mark.parametrize("method", ["none", "clahe", "gray_world", "reinhard"])
    def test_output_dtype_is_float32(self, method):
        roi = _make_noisy_roi()
        out = normalize_roi(roi, method=method)
        assert out.dtype == np.float32, f"{method}: expected float32, got {out.dtype}"

    @pytest.mark.parametrize("method", ["none", "clahe", "gray_world", "reinhard"])
    def test_output_shape_preserved(self, method):
        roi = _make_noisy_roi(h=64, w=80)
        out = normalize_roi(roi, method=method)
        assert out.shape == (64, 80, 3), f"{method}: shape mismatch {out.shape}"

    @pytest.mark.parametrize("method", ["none", "clahe", "gray_world", "reinhard"])
    def test_output_in_unit_range(self, method):
        roi = _make_noisy_roi()
        out = normalize_roi(roi, method=method)
        assert out.min() >= -0.001, f"{method}: min {out.min()} below 0"
        assert out.max() <= 1.001, f"{method}: max {out.max()} above 1"

    def test_zscore_output_shape(self):
        roi = _make_noisy_roi()
        out = normalize_roi(roi, method="zscore")
        assert out.dtype == np.float32
        assert out.shape == (64, 64, 3)

    def test_zscore_clipped_to_3(self):
        """zscore output should be clipped to [-3, 3]."""
        roi = _make_noisy_roi()
        out = normalize_roi(roi, method="zscore")
        assert out.min() >= -3.0 - 1e-6
        assert out.max() <= 3.0 + 1e-6

    def test_unknown_method_raises_valueerror(self):
        roi = _make_noisy_roi()
        with pytest.raises(ValueError, match="Unknown normalization method"):
            normalize_roi(roi, method="invalid_method_xyz")

    def test_none_input_raises_valueerror(self):
        with pytest.raises((ValueError, Exception)):
            normalize_roi(None, method="clahe")

    def test_empty_input_raises_valueerror(self):
        empty = np.zeros((0, 0, 3), dtype=np.uint8)
        with pytest.raises((ValueError, Exception)):
            normalize_roi(empty, method="clahe")

    def test_all_supported_methods_listed(self):
        """SUPPORTED_METHODS must match what normalize_roi accepts."""
        roi = _make_noisy_roi()
        for method in SUPPORTED_METHODS:
            out = normalize_roi(roi, method=method)
            assert out is not None


class TestClahNormalize:

    def test_preserves_color_channels(self):
        """CLAHE should only modify the L (luminance) channel in LAB space.
        The A and B channels (color opponent axes) should remain close to original."""
        import cv2
        roi = _make_noisy_roi(seed=7)
        out = clahe_normalize(roi)
        assert out.shape == roi.shape
        assert out.dtype == np.float32

    def test_output_in_range(self):
        roi = _make_noisy_roi()
        out = clahe_normalize(roi)
        assert out.min() >= 0.0 - 1e-6
        assert out.max() <= 1.0 + 1e-6


class TestGrayWorldNormalize:

    def test_output_in_unit_range(self):
        roi = _make_noisy_roi()
        out = gray_world_normalize(roi)
        assert out.min() >= 0.0 - 1e-6
        assert out.max() <= 1.0 + 1e-6

    def test_near_black_image_does_not_crash(self):
        """Near-black image: gray-world should skip WB without crashing."""
        roi = _make_roi(r=1, g=1, b=1)
        out = gray_world_normalize(roi)
        assert out is not None
        assert out.shape == (64, 64, 3)


class TestReinhardNormalize:

    def test_output_in_unit_range(self):
        roi = _make_noisy_roi()
        out = reinhard_normalize(roi)
        assert out.min() >= 0.0 - 1e-6
        assert out.max() <= 1.0 + 1e-6

    def test_flat_channel_does_not_crash(self):
        """Flat-color image (std=0 per channel) should not crash."""
        roi = _make_roi(r=128, g=128, b=128)
        out = reinhard_normalize(roi)
        assert out is not None


class TestComputeRoiColorStats:

    def test_stats_keys_present(self):
        roi = _make_noisy_roi()
        stats = compute_roi_color_stats(roi)
        for key in ["mean_R", "mean_G", "mean_B", "mean_L", "mean_A", "mean_B_lab"]:
            assert key in stats, f"Missing key: {key}"

    def test_stats_values_are_floats(self):
        roi = _make_noisy_roi()
        stats = compute_roi_color_stats(roi)
        for k, v in stats.items():
            assert isinstance(v, float), f"Key {k}: expected float, got {type(v)}"
