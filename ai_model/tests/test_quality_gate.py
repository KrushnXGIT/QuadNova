"""
test_quality_gate.py
====================
Tests for the ImageQualityGate in src/vision/quality_gate.py.

Covers every rejection condition:
  - blur
  - too dark
  - too bright
  - low resolution
  - poor ROI coverage
  - ROI detection failure (coverage=0.0)
  - accepted image passes gate
"""

import numpy as np
import pytest

from src.vision.quality_gate import ImageQualityGate, make_quality_gate


# ---------------------------------------------------------------------------
# Helpers to build synthetic test images
# ---------------------------------------------------------------------------

def _make_rgb(h=200, w=200, brightness=128, dtype=np.uint8):
    """Create a flat-color RGB image."""
    return np.full((h, w, 3), brightness, dtype=dtype)


def _make_sharp_rgb(h=200, w=200, brightness=128):
    """Create a high-variance (sharp-looking) image with a checkerboard pattern."""
    img = np.zeros((h, w, 3), dtype=np.uint8)
    for y in range(h):
        for x in range(w):
            v = 255 if (x // 4 + y // 4) % 2 == 0 else brightness
            img[y, x] = [v, v, v]
    return img


def _make_blurry_rgb(h=200, w=200):
    """Create a near-flat image that will have very low Laplacian variance (blurry)."""
    return np.full((h, w, 3), 128, dtype=np.uint8)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestImageQualityGate:

    def setup_method(self):
        """Use strict thresholds so synthetic images hit the right conditions."""
        self.gate = ImageQualityGate(
            blur_threshold=100.0,    # high threshold so flat images fail blur
            dark_threshold=30.0,
            bright_threshold=220.0,
            min_dimension=100,
            min_roi_coverage=0.01,
        )

    def test_accepted_sharp_image(self):
        """A sharp, well-lit image should pass the gate."""
        img = _make_sharp_rgb(brightness=128)
        result = self.gate.check(img)
        assert result["quality_status"] == "ACCEPTED", \
            f"Expected ACCEPTED, got {result['quality_status']}: {result['failure_reasons']}"
        assert result["quality_score"] >= 0.0
        assert result["quality_score"] <= 1.0
        assert len(result["failure_reasons"]) == 0

    def test_rejected_blurry_image(self):
        """A flat (blurry) image should fail the blur check."""
        img = _make_blurry_rgb()
        result = self.gate.check(img)
        assert result["quality_status"] == "REJECTED"
        assert any("BLURRY" in r or "blurry" in r.lower() for r in result["failure_reasons"]), \
            f"Expected blur rejection, got: {result['failure_reasons']}"

    def test_rejected_too_dark(self):
        """A near-black image should fail the darkness check."""
        img = _make_rgb(brightness=5)  # very dark
        result = self.gate.check(img)
        assert result["quality_status"] == "REJECTED"
        assert any("DARK" in r or "dark" in r.lower() for r in result["failure_reasons"]), \
            f"Expected dark rejection, got: {result['failure_reasons']}"

    def test_rejected_too_bright(self):
        """A near-white image should fail the brightness check."""
        img = _make_rgb(brightness=255)  # blown out
        result = self.gate.check(img)
        assert result["quality_status"] == "REJECTED"
        assert any("BRIGHT" in r or "bright" in r.lower() for r in result["failure_reasons"]), \
            f"Expected bright rejection, got: {result['failure_reasons']}"

    def test_rejected_low_resolution(self):
        """An image smaller than min_dimension should fail resolution check."""
        img = _make_sharp_rgb(h=50, w=50, brightness=128)
        gate = ImageQualityGate(min_dimension=100, blur_threshold=1.0)  # relaxed blur
        result = gate.check(img)
        assert result["quality_status"] == "REJECTED"
        assert any("RESOLUTION" in r or "resolution" in r.lower() or "small" in r.lower()
                   for r in result["failure_reasons"]), \
            f"Expected resolution rejection, got: {result['failure_reasons']}"

    def test_rejected_poor_roi_coverage(self):
        """A very low ROI coverage fraction should fail coverage check."""
        img = _make_sharp_rgb(brightness=128)
        gate = ImageQualityGate(blur_threshold=1.0, min_roi_coverage=0.05)
        result = gate.check(img, coverage_fraction=0.001)
        assert result["quality_status"] == "REJECTED"
        assert any("COVERAGE" in r or "coverage" in r.lower() for r in result["failure_reasons"]), \
            f"Expected coverage rejection, got: {result['failure_reasons']}"

    def test_rejected_roi_detection_failure(self):
        """coverage_fraction=0.0 signals ROI detection failure."""
        img = _make_sharp_rgb(brightness=128)
        gate = ImageQualityGate(blur_threshold=1.0, min_roi_coverage=0.001)
        result = gate.check(img, coverage_fraction=0.0)
        assert result["quality_status"] == "REJECTED"
        # Should contain coverage or detection failure reason
        assert len(result["failure_reasons"]) >= 1

    def test_quality_score_is_float_in_unit_range(self):
        """quality_score must always be in [0, 1]."""
        for brightness in [5, 60, 128, 200, 255]:
            img = _make_rgb(brightness=brightness)
            result = self.gate.check(img)
            assert 0.0 <= result["quality_score"] <= 1.0, \
                f"quality_score={result['quality_score']} out of [0,1] for brightness={brightness}"

    def test_quality_score_is_not_medical_confidence(self):
        """Verify the disclaimer field is present."""
        img = _make_sharp_rgb(brightness=128)
        result = self.gate.check(img)
        assert "_disclaimer" in result
        assert "medical" in result["_disclaimer"].lower() or "not" in result["_disclaimer"].lower()

    def test_check_details_always_returned(self):
        """check_details dict should always be present."""
        img = _make_sharp_rgb(brightness=128)
        result = self.gate.check(img)
        assert "check_details" in result
        assert isinstance(result["check_details"], dict)

    def test_make_quality_gate_factory(self):
        """make_quality_gate() should respect overrides."""
        gate = make_quality_gate({"blur_threshold": 99.9})
        assert gate.blur_threshold == 99.9

    def test_invalid_input_none(self):
        """None input should not crash — should return REJECTED."""
        result = self.gate.check(None)
        # Should fail gracefully — quality gate wraps check_image_quality which handles None
        assert result["quality_status"] == "REJECTED"

    def test_accepted_image_has_no_failure_reasons(self):
        """Accepted images should have empty failure_reasons list."""
        img = _make_sharp_rgb(brightness=128)
        gate = ImageQualityGate(blur_threshold=1.0)  # very relaxed blur
        result = gate.check(img)
        if result["quality_status"] == "ACCEPTED":
            assert result["failure_reasons"] == []
