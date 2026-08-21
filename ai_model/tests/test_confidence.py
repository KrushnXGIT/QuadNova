"""
test_confidence.py
==================
Tests for:
  - src/model/confidence.py  (ConfidenceCalibrator)
  - src/model/decision.py    (HbDecisionSystem)

Covers:
  - Uncertainty calibration from validation data
  - Confidence status mapping
  - Decision system output structure
  - RETAKE_IMAGE for rejected images
  - CONFIRMATORY_TEST for high uncertainty
  - Screening estimate for acceptable uncertainty
  - No fake Hb values in output
  - Output schema completeness
"""

import json
import numpy as np
import pytest
from pathlib import Path

from src.model.confidence import ConfidenceCalibrator
from src.model.decision import HbDecisionSystem, MODEL_VERSION


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def calibrated_calibrator():
    """A calibrator trained on synthetic validation data."""
    rng = np.random.default_rng(42)
    n = 30
    # Simulate: higher uncertainty → higher error
    uncertainties = rng.uniform(0.1, 2.0, size=n)
    errors = uncertainties * 0.8 + rng.uniform(0.0, 0.5, size=n)
    cal = ConfidenceCalibrator()
    cal.calibrate(uncertainties, errors)
    return cal


@pytest.fixture
def decision_system(calibrated_calibrator):
    return HbDecisionSystem(calibrator=calibrated_calibrator)


# ---------------------------------------------------------------------------
# ConfidenceCalibrator tests
# ---------------------------------------------------------------------------

class TestConfidenceCalibrator:

    def test_calibrate_sets_thresholds(self, calibrated_calibrator):
        cal = calibrated_calibrator
        assert cal.calibrated is True
        assert cal.low_uncertainty_threshold > 0
        assert cal.high_uncertainty_threshold > cal.low_uncertainty_threshold

    def test_thresholds_derived_from_validation_data(self, calibrated_calibrator):
        """Thresholds should be derived from validation data (not hardcoded)."""
        cal = calibrated_calibrator
        # With the synthetic data: low_t should be ~33rd percentile of uncertainties
        rng = np.random.default_rng(42)
        uncertainties = rng.uniform(0.1, 2.0, size=30)
        expected_t33 = np.percentile(uncertainties, 33)
        assert abs(cal.low_uncertainty_threshold - expected_t33) < 0.2

    def test_returns_high_confidence_for_low_uncertainty(self, calibrated_calibrator):
        cal = calibrated_calibrator
        low_unc = cal.low_uncertainty_threshold * 0.5  # well below threshold
        status = cal.get_confidence_status(low_unc, quality_score=0.9, quality_status="ACCEPTED")
        assert status == "HIGH_CONFIDENCE"

    def test_returns_low_confidence_for_high_uncertainty(self, calibrated_calibrator):
        cal = calibrated_calibrator
        high_unc = cal.high_uncertainty_threshold * 2.0  # well above threshold
        status = cal.get_confidence_status(high_unc, quality_score=0.9, quality_status="ACCEPTED")
        assert status == "LOW_CONFIDENCE"

    def test_rejected_image_always_low_confidence(self, calibrated_calibrator):
        cal = calibrated_calibrator
        # Even with near-zero uncertainty, a rejected image → LOW_CONFIDENCE
        status = cal.get_confidence_status(0.0, quality_score=1.0, quality_status="REJECTED")
        assert status == "LOW_CONFIDENCE"

    def test_calibration_stats_returned(self):
        cal = ConfidenceCalibrator()
        rng = np.random.default_rng(0)
        unc = rng.uniform(0.1, 1.5, 20)
        err = unc + rng.uniform(0, 0.2, 20)
        stats = cal.calibrate(unc, err)
        assert "n_validation" in stats
        assert "calibration_monotonic" in stats
        assert "ci95_coverage_fraction" in stats
        assert "pearson_correlation_uncertainty_error" in stats

    def test_save_and_load(self, tmp_path, calibrated_calibrator):
        cal = calibrated_calibrator
        save_path = str(tmp_path / "calibration.json")
        cal.save(save_path)
        loaded = ConfidenceCalibrator.load(save_path)
        assert loaded.calibrated == cal.calibrated
        assert abs(loaded.low_uncertainty_threshold - cal.low_uncertainty_threshold) < 1e-6
        assert abs(loaded.high_uncertainty_threshold - cal.high_uncertainty_threshold) < 1e-6

    def test_small_sample_warning(self):
        """Small validation set should generate a warning note."""
        cal = ConfidenceCalibrator()
        unc = np.array([0.5, 0.8, 0.3])
        err = np.array([0.4, 0.7, 0.2])
        stats = cal.calibrate(unc, err)
        assert any("WARNING" in note or "small" in note.lower() for note in stats["calibration_notes"])

    def test_empty_arrays_raise_clear_error(self):
        cal = ConfidenceCalibrator()
        with pytest.raises(ValueError, match="non-empty"):
            cal.calibrate(np.array([]), np.array([]))

    def test_invalid_numeric_values_are_rejected(self):
        cal = ConfidenceCalibrator()
        with pytest.raises(ValueError, match="finite"):
            cal.calibrate(np.array([0.1, np.nan]), np.array([0.2, 0.3]))


# ---------------------------------------------------------------------------
# HbDecisionSystem tests
# ---------------------------------------------------------------------------

class TestHbDecisionSystem:

    def test_retake_image_for_rejected(self, decision_system):
        output = decision_system.decide(
            estimated_hb=None,
            uncertainty=None,
            quality_status="REJECTED",
            quality_score=0.1,
            failure_reasons=["TOO_BLURRY: Laplacian_var=3.0 < threshold 10.0"],
        )
        assert output["recommendation"] == "RETAKE_IMAGE"
        assert output["estimated_hb_g_dl"] is None
        assert output["image_quality_status"] == "REJECTED"

    def test_confirmatory_test_for_high_uncertainty(self, decision_system, calibrated_calibrator):
        high_unc = calibrated_calibrator.high_uncertainty_threshold * 2.5
        output = decision_system.decide(
            estimated_hb=10.5,
            uncertainty=high_unc,
            quality_status="ACCEPTED",
            quality_score=0.75,
            failure_reasons=[],
        )
        assert output["recommendation"] in (
            "CONFIRMATORY_TEST_RECOMMENDED",
            "SCREENING_ESTIMATE_LOW_CONFIDENCE"
        )
        assert output["confidence_status"] in ("LOW_CONFIDENCE", "MEDIUM_CONFIDENCE")

    def test_screening_estimate_for_low_uncertainty(self, decision_system, calibrated_calibrator):
        low_unc = calibrated_calibrator.low_uncertainty_threshold * 0.3
        output = decision_system.decide(
            estimated_hb=12.5,
            uncertainty=low_unc,
            quality_status="ACCEPTED",
            quality_score=0.9,
            failure_reasons=[],
        )
        assert output["confidence_status"] == "HIGH_CONFIDENCE"
        assert output["recommendation"] == "SCREENING_ESTIMATE"

    def test_output_schema_complete(self, decision_system):
        """Output must have all required keys."""
        output = decision_system.decide(
            estimated_hb=11.0,
            uncertainty=0.5,
            quality_status="ACCEPTED",
            quality_score=0.8,
            failure_reasons=[],
        )
        required_keys = [
            "estimated_hb_g_dl",
            "hb_std_g_dl",
            "confidence_interval_95",
            "confidence_status",
            "image_quality_status",
            "image_quality_score",
            "recommendation",
            "recommendation_text",
            "model_version",
            "_disclaimer",
        ]
        for key in required_keys:
            assert key in output, f"Missing required key: {key}"

    def test_no_hardcoded_hb_values(self, decision_system):
        """Output estimated_hb_g_dl must match the input, not be a hardcoded constant."""
        for test_hb in [7.5, 10.0, 14.3, 17.1]:
            output = decision_system.decide(
                estimated_hb=test_hb,
                uncertainty=0.3,
                quality_status="ACCEPTED",
                quality_score=0.85,
                failure_reasons=[],
            )
            assert abs(output["estimated_hb_g_dl"] - test_hb) < 0.01, \
                f"Expected hb={test_hb}, got {output['estimated_hb_g_dl']}"

    def test_confidence_interval_contains_estimate(self, decision_system):
        """The 95% CI should be centered around the estimate."""
        output = decision_system.decide(
            estimated_hb=12.0,
            uncertainty=1.0,
            quality_status="ACCEPTED",
            quality_score=0.8,
            failure_reasons=[],
        )
        ci = output["confidence_interval_95"]
        assert ci is not None
        assert len(ci) == 2
        assert ci[0] < 12.0 < ci[1]
        # CI should be estimate ± 1.96 * std
        assert abs(ci[0] - (12.0 - 1.96 * 1.0)) < 0.1
        assert abs(ci[1] - (12.0 + 1.96 * 1.0)) < 0.1

    def test_model_version_is_string(self, decision_system):
        output = decision_system.decide(
            estimated_hb=11.0,
            uncertainty=0.5,
            quality_status="ACCEPTED",
            quality_score=0.8,
            failure_reasons=[],
        )
        assert isinstance(output["model_version"], str)
        assert len(output["model_version"]) > 0

    def test_disclaimer_always_present(self, decision_system):
        """_disclaimer must never be omitted or empty."""
        for quality_status in ["ACCEPTED", "REJECTED"]:
            output = decision_system.decide(
                estimated_hb=11.0 if quality_status == "ACCEPTED" else None,
                uncertainty=0.5 if quality_status == "ACCEPTED" else None,
                quality_status=quality_status,
                quality_score=0.5,
                failure_reasons=[] if quality_status == "ACCEPTED" else ["TOO_BLURRY"],
            )
            assert "_disclaimer" in output
            assert len(output["_disclaimer"]) > 0

    def test_image_quality_score_in_unit_range(self, decision_system):
        """image_quality_score must be in [0, 1]."""
        for score in [0.0, 0.5, 1.0]:
            output = decision_system.decide(
                estimated_hb=11.0,
                uncertainty=0.5,
                quality_status="ACCEPTED",
                quality_score=score,
                failure_reasons=[],
            )
            assert 0.0 <= output["image_quality_score"] <= 1.0

    def test_no_fake_hb_values(self, decision_system):
        """The decision system must not invent Hb values (e.g., from NFHS data)."""
        output = decision_system.decide(
            estimated_hb=None,
            uncertainty=None,
            quality_status="REJECTED",
            quality_score=0.1,
            failure_reasons=["TOO_BLURRY"],
        )
        assert output["estimated_hb_g_dl"] is None, \
            "Rejected image must return estimated_hb_g_dl=None, not a fake value"

    def test_missing_estimate_is_not_fabricated_when_quality_accepted(self, decision_system):
        output = decision_system.decide(
            estimated_hb=None,
            uncertainty=0.5,
            quality_status="ACCEPTED",
            quality_score=0.8,
            failure_reasons=[],
        )
        assert output["estimated_hb_g_dl"] is None
        assert output["confidence_status"] == "LOW_CONFIDENCE"
        assert output["recommendation"] == "CONFIRMATORY_TEST_RECOMMENDED"

    def test_subject_leakage_check_not_bypassed(self):
        """Decision system must not use population statistics as individual Hb labels."""
        # This is a sanity check: the decision system should not have any hardcoded
        # Hb thresholds that falsely imply a clinical diagnosis.
        from src.model.decision import HbDecisionSystem
        ds = HbDecisionSystem()
        # Output recommendation should NOT say 'anaemia' or 'haemoglobin deficiency'
        # as a definitive statement — it should be a screening estimate
        output = ds.decide(
            estimated_hb=8.0,
            uncertainty=0.5,
            quality_status="ACCEPTED",
            quality_score=0.8,
            failure_reasons=[],
        )
        rtext = output.get("recommendation_text", "").lower()
        assert "screening" in rtext or "estimate" in rtext or "confirmatory" in rtext, \
            f"Recommendation text should say 'screening estimate', got: {rtext}"
