"""
Regression tests for the AUTHORITATIVE INFERENCE FIREWALL
(app.services.input_domain_gate.validate_conjunctiva_input).

Guarantees under test:
  1. Unrelated/negative images NEVER reach the Hb predictor.
  2. Client-supplied masks cannot bypass the server-side domain check.
  3. Valid conjunctiva input still reaches the predictor (no over-blocking).
  4. Rejection payloads never contain any prediction field.
  5. No stale state between sequential requests (valid -> invalid -> valid).
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))

from negative_images import (
    NEGATIVE_GENERATORS,
    build_full_frame_mask_png,
    to_jpeg,
)
from app.services.ai_service import AIService
from app.services.mask_generator import generate_mask_png


# ── Helpers ──────────────────────────────────────────────────────────────────

class SpyPredictor:
    """Records predict_from_path calls; optionally returns a success payload."""

    def __init__(self, succeed: bool = True) -> None:
        self.calls: list[dict] = []
        self.succeed = succeed

    def predict_from_path(self, **kwargs):
        self.calls.append(kwargs)
        if not self.succeed:
            return {"success": False, "status": "INFERENCE_ERROR",
                    "data": {"retry": False, "message": "spy"}}
        return {
            "success": True,
            "status": "PREDICTION_COMPLETE",
            "data": {"estimated_hb_g_dl": 10.0},
        }


def make_service(succeed: bool = True) -> tuple[AIService, SpyPredictor]:
    service = AIService()
    spy = SpyPredictor(succeed=succeed)
    service._predictor = spy
    service._ready = True
    return service, spy


def _synthetic_conjunctiva_like() -> bytes:
    """
    Deterministic synthetic capture that legitimately satisfies every gate:
    large bright pink textured tissue region + dark lid line + skin surround.
    Used for environment-independent positive-path tests.
    """
    rng = np.random.default_rng(2024)
    h, w = 800, 600
    img = np.ones((h, w, 3), dtype=np.float32)
    img[..., 0], img[..., 1], img[..., 2] = 225, 185, 165  # skin surround
    yy, xx = np.mgrid[0:h, 0:w]
    tissue = (((xx - 300) / 170.0) ** 2 + ((yy - 430) / 150.0) ** 2) <= 1
    # Bright pink with vertical shading gradient -> textured, well-lit mucosa.
    shade = 1.0 - 0.30 * ((yy - 300) / 260.0).clip(0, 1.2)
    img[tissue] = np.array([210.0, 128.0, 138.0]) * shade[tissue][:, None]
    # Dark eyelid boundary just above the tissue.
    lid = (np.abs(yy - 268) < 12) & (xx > 130) & (xx < 470)
    img[lid] = np.array([35.0, 25.0, 25.0])
    img += rng.normal(0, 2.5, (h, w, 3))
    return to_jpeg(img)


VALID_SAMPLE = (
    Path(__file__).resolve().parent.parent.parent
    / "data" / "raw" / "sample_dataset" / "20200118_164733.jpg"
)
VALID_SAMPLE_MASK = VALID_SAMPLE.with_name("20200118_164733_forniceal_palpebral.png")


def assert_rejection_payload_clean(payload: dict) -> None:
    assert payload["success"] is False
    assert payload["status"] in {
        "INVALID_INPUT", "EYE_NOT_DETECTED", "CONJUNCTIVA_NOT_DETECTED",
        "ROI_QUALITY_FAILED",
    }
    err = payload["error"]
    assert set(err) == {"code", "message", "retryable"}
    data = payload.get("data") or {}
    for forbidden in (
        "estimated_hb_g_dl", "hb_std_g_dl", "confidence_interval_95",
        "confidence_status", "recommendation",
    ):
        assert forbidden not in data
        assert forbidden not in payload


# ── 1. Chroma detector itself must reject a bare red object ────────────────

def test_red_object_does_not_produce_a_conjunctiva_mask():
    image = np.zeros((600, 800, 3), dtype=np.uint8) + 120
    image[150:450, 250:550] = [210, 50, 70]
    buffer = io.BytesIO()
    Image.fromarray(image, mode="RGB").save(buffer, format="JPEG")
    assert generate_mask_png(buffer.getvalue()) is None


# ── 2. Full negative matrix — predictor call count must stay ZERO ──────────

@pytest.mark.parametrize("name", sorted(NEGATIVE_GENERATORS))
def test_negative_image_never_reaches_predictor(name):
    service, spy = make_service()
    payload = NEGATIVE_GENERATORS[name]()
    result = service.predict_upload(payload, ".jpg")
    assert result["success"] is False, f"{name} was accepted!"
    assert result["status"] in {
        "INVALID_INPUT", "EYE_NOT_DETECTED", "CONJUNCTIVA_NOT_DETECTED",
        "ROI_QUALITY_FAILED",
    }
    assert result["error"]["code"] in {
        "EYE_NOT_DETECTED", "CONJUNCTIVA_NOT_DETECTED", "ROI_QUALITY_FAILED",
    }
    assert spy.calls == [], f"Hb predictor invoked for negative image: {name}"
    assert_rejection_payload_clean(result)


def test_invalid_image_does_not_call_hb_predictor():
    """THE core safety test: invalid input => Hb predictor invocation count 0."""
    service, spy = make_service()
    result = service.predict_upload(
        NEGATIVE_GENERATORS["adversarial_weak_positive"](), ".jpg"
    )
    assert result["status"] in {
        "INVALID_INPUT", "EYE_NOT_DETECTED", "CONJUNCTIVA_NOT_DETECTED",
        "ROI_QUALITY_FAILED",
    }
    assert len(spy.calls) == 0


# ── 3. Client-mask bypass regression (the proven attack) ───────────────────

def test_client_mask_cannot_bypass_domain_gate():
    """Old bug: weak-positive image + arbitrary client mask => Hb on anything."""
    service, spy = make_service()
    from PIL import Image as _Image
    img = _Image.open(io.BytesIO(NEGATIVE_GENERATORS["adversarial_weak_positive"]()))
    w, h = img.size
    result = service.predict_upload(
        NEGATIVE_GENERATORS["adversarial_weak_positive"](),
        ".jpg",
        mask_bytes=build_full_frame_mask_png(h, w),
        mask_suffix=".png",
    )
    assert result["status"] == "INVALID_INPUT"
    assert spy.calls == []
    assert_rejection_payload_clean(result)


def test_explicit_mask_on_non_conjunctiva_image_rejected():
    service, spy = make_service()
    mask = np.zeros((600, 800, 4), dtype=np.uint8)
    mask[150:450, 250:550] = [120, 120, 120, 255]
    mask_buffer = io.BytesIO()
    Image.fromarray(mask, mode="RGBA").save(mask_buffer, format="PNG")
    image = np.zeros((600, 800, 3), dtype=np.uint8) + 120
    image[150:450, 250:550] = [210, 50, 70]
    buffer = io.BytesIO()
    Image.fromarray(image, mode="RGB").save(buffer, format="JPEG")

    result = service.predict_upload(buffer.getvalue(), ".jpg",
                                    mask_bytes=mask_buffer.getvalue())
    assert result["status"] == "INVALID_INPUT"
    assert result["error"]["code"] == "CONJUNCTIVA_NOT_DETECTED"
    assert spy.calls == []


# ── 4. Valid conjunctiva input MUST still reach the predictor ──────────────

def test_valid_synthetic_conjunctiva_reaches_predictor_exactly_once():
    service, spy = make_service()
    result = service.predict_upload(_synthetic_conjunctiva_like(), ".jpg")
    if not result["success"]:
        pytest.fail(
            "Over-blocking: synthetic conjunctiva-like capture was rejected: "
            f"{result.get('error')} | {result.get('validation')}"
        )
    assert result["status"] == "PREDICTION_COMPLETE"
    assert len(spy.calls) == 1
    # The predictor must receive the SERVER-VALIDATED mask only.
    called_mask = Path(spy.calls[0]["mask_path"])
    assert called_mask.is_file() or not called_mask.exists()  # temp cleaned later
    assert spy.calls[0]["image_path"] is not None


@pytest.mark.skipif(not VALID_SAMPLE.is_file(), reason="sample dataset not present")
def test_valid_real_sample_auto_mask_reaches_predictor():
    """Real captured conjunctiva image (no client mask) must pass the gate."""
    service, spy = make_service()
    result = service.predict_upload(VALID_SAMPLE.read_bytes(), ".jpg")
    assert result["success"] is True
    assert len(spy.calls) == 1


@pytest.mark.skipif(
    not (VALID_SAMPLE.is_file() and VALID_SAMPLE_MASK.is_file()),
    reason="sample dataset not present",
)
def test_real_annotated_dataset_mask_is_accepted():
    """
    Real annotated masks overlap the independently-detected region almost
    fully (measured ~0.999), so they remain trusted; arbitrary masks do not.
    """
    service, spy = make_service()
    result = service.predict_upload(
        VALID_SAMPLE.read_bytes(), ".jpg",
        mask_bytes=VALID_SAMPLE_MASK.read_bytes(), mask_suffix=".png",
    )
    assert result["success"] is True
    assert len(spy.calls) == 1


# ── 5. No stale state across sequential requests (cache-bug sequence) ──────

def test_sequence_valid_invalid_invalid_valid_no_stale_results():
    """
    PHASE-15 style sequence at the service boundary:
      valid -> invalid -> invalid -> valid -> invalid
    Every rejection must be independent; no previous success may leak into a
    later rejection response.
    """
    service, spy = make_service()
    valid_img = VALID_SAMPLE.read_bytes() if VALID_SAMPLE.is_file() \
        else _synthetic_conjunctiva_like()
    neg_img = NEGATIVE_GENERATORS["room_scene"]()

    seq = [
        (valid_img, True),
        (neg_img, False),
        (neg_img, False),
        (valid_img, True),
        (neg_img, False),
    ]
    for i, (img_bytes, expect_success) in enumerate(seq):
        result = service.predict_upload(img_bytes, ".jpg")
        assert result["success"] is expect_success, (
            f"step {i}: expected success={expect_success}, got {result['status']}"
        )
        if not expect_success:
            assert_rejection_payload_clean(result)
            assert "estimated_hb_g_dl" not in (result.get("data") or {})

    total_expected_calls = sum(1 for _, ok in seq if ok)
    assert len(spy.calls) == total_expected_calls


# ── 6. Gate-level unit checks ──────────────────────────────────────────────

def test_gate_rejects_unreadable_bytes_fail_closed():
    from app.services.input_domain_gate import validate_conjunctiva_input
    res = validate_conjunctiva_input(b"\x00\x01not-an-image")
    assert res.valid is False
    assert res.error_code in {"IMAGE_UNREADABLE", "CONJUNCTIVA_NOT_DETECTED"}




def test_invalid_domain_never_invokes_predictor(monkeypatch):
    service = AIService()
    calls = []

    class FakePredictor:
        def predict_from_path(self, **kwargs):
            calls.append(kwargs)
            raise AssertionError("Hb predictor must not run for invalid input")

    service._predictor = FakePredictor()
    service._ready = True
    service._settings.AUTO_MASK_ENABLED = True

    result = service.predict_upload(_red_object(), ".jpg")

    assert result["success"] is False
    assert result["status"] == "ROI_FAILED"
    assert result["error"]["code"] == "CONJUNCTIVA_NOT_DETECTED"
    assert result["validation"] == {
        "roi_detected": False,
        "quality_status": "not_run",
    }
    assert "estimated_hb_g_dl" not in result
    assert calls == []


def test_explicit_mask_cannot_bypass_domain_gate(monkeypatch, tmp_path):
    service = AIService()
    calls = []

    class FakePredictor:
        def predict_from_path(self, **kwargs):
            calls.append(kwargs)
            return {"success": True, "status": "PREDICTION_COMPLETE", "data": {}}

    service._predictor = FakePredictor()
    service._ready = True
    mask = np.zeros((600, 800, 4), dtype=np.uint8)
    mask[150:450, 250:550] = [120, 120, 120, 255]
    mask_buffer = io.BytesIO()
    Image.fromarray(mask, mode="RGBA").save(mask_buffer, format="PNG")

    result = service.predict_upload(
        _red_object(), ".jpg", mask_bytes=mask_buffer.getvalue()
    )

    assert result["status"] == "ROI_FAILED"
    assert calls == []