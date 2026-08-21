"""
Backend test suite.

Tests confirm:
  1. All endpoints respond correctly
  2. MODEL_NOT_READY path works and NEVER returns a fake Hb value
  3. Error responses are structured correctly for Flutter parsing
  4. Image validation rejects bad inputs

Run:
    cd backend
    pip install -r requirements.txt
    pytest tests/ -v
"""
import io
import pytest
from fastapi.testclient import TestClient
from PIL import Image
import numpy as np

# Patch model service before app import so tests don't need a real model
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.main import app
from app.utils import validation

client = TestClient(app)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_jpeg_bytes(width: int = 300, height: int = 300) -> bytes:
    """Generate a valid in-memory JPEG image."""
    arr = np.random.randint(80, 180, (height, width, 3), dtype=np.uint8)
    img = Image.fromarray(arr, mode="RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def _make_png_bytes(width: int = 300, height: int = 300) -> bytes:
    arr = np.random.randint(80, 180, (height, width, 3), dtype=np.uint8)
    img = Image.fromarray(arr, mode="RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ── 1. Health endpoint ────────────────────────────────────────────────────────

def test_health_returns_ok():
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["service"] == "anaemia-screening-backend"


# ── 2. Model status ───────────────────────────────────────────────────────────

def test_model_status_returns_not_ready_without_model():
    r = client.get("/api/v1/model/status")
    assert r.status_code == 200
    body = r.json()
    assert "available" in body
    assert "model" in body
    assert "status" in body
    # Without a real model file the adapter must report not ready
    assert body["available"] is False
    assert body["status"] == "MODEL_NOT_READY"


# ── 3. Missing image ──────────────────────────────────────────────────────────

def test_predict_missing_image_returns_422():
    r = client.post("/api/v1/predict")
    assert r.status_code == 422


# ── 4. Invalid / non-image file ───────────────────────────────────────────────

def test_predict_invalid_image_content():
    r = client.post(
        "/api/v1/predict",
        files={"image": ("test.jpg", b"not-an-image-at-all", "image/jpeg")},
    )
    assert r.status_code in (400, 422)
    body = r.json()
    assert body["success"] is False
    assert "status" in body
    assert "message" in body


# ── 5. Unsupported format ─────────────────────────────────────────────────────

def test_predict_unsupported_format_rejected():
    r = client.post(
        "/api/v1/predict",
        files={"image": ("test.gif", b"GIF89a...", "image/gif")},
    )
    assert r.status_code in (400, 415, 422)
    body = r.json()
    assert body["success"] is False


# ── 6. Oversized image ────────────────────────────────────────────────────────

def test_predict_oversized_image_rejected():
    # 11 MB of zeros — exceeds default MAX_UPLOAD_SIZE_MB=10
    big_data = b"\x00" * (11 * 1024 * 1024)
    r = client.post(
        "/api/v1/predict",
        files={"image": ("big.jpg", big_data, "image/jpeg")},
    )
    assert r.status_code == 413
    body = r.json()
    assert body["success"] is False


# ── 7. Valid image — model not ready path ─────────────────────────────────────

def test_predict_valid_image_model_not_ready():
    """
    A valid JPEG with no model loaded must return MODEL_NOT_READY.
    It must NEVER return a fake Hb value.
    """
    jpeg = _make_jpeg_bytes()
    r = client.post(
        "/api/v1/predict",
        files={"image": ("eye.jpg", jpeg, "image/jpeg")},
    )
    body = r.json()

    # Must be MODEL_NOT_READY (503) or IMAGE_QUALITY_FAILED (422)
    # — either way, NO fake Hb value should appear
    assert body["success"] is False
    assert "data" not in body or "estimated_hb" not in (body.get("data") or {})
    assert body["status"] in ("MODEL_NOT_READY", "IMAGE_QUALITY_FAILED")


# ── 8. No fake Hb value ever returned ────────────────────────────────────────

def test_no_fake_hb_returned_when_model_absent():
    """
    Core safety test: backend must never invent an Hb value.
    When model is absent, response.data must not contain estimated_hb.
    """
    jpeg = _make_jpeg_bytes()
    r = client.post(
        "/api/v1/predict",
        files={"image": ("eye.jpg", jpeg, "image/jpeg")},
    )
    body = r.json()
    data = body.get("data", {}) or {}
    assert "estimated_hb" not in data, (
        f"Backend returned a fake Hb value when model is absent: {data}"
    )


# ── 9. Error response structure ───────────────────────────────────────────────

def test_error_response_has_required_fields():
    """All error responses must have success, status, message — no stack traces."""
    r = client.post(
        "/api/v1/predict",
        files={"image": ("bad.jpg", b"garbage", "image/jpeg")},
    )
    body = r.json()
    assert "success" in body
    assert "status" in body
    assert "message" in body
    # No Python internals exposed
    assert "traceback" not in str(body).lower()
    assert "exception" not in str(body).lower()


# ── 10. PNG format accepted ───────────────────────────────────────────────────

def test_predict_png_accepted():
    png = _make_png_bytes()
    r = client.post(
        "/api/v1/predict",
        files={"image": ("eye.png", png, "image/png")},
    )
    body = r.json()
    # Any structured response is fine — just not a 500 crash
    assert r.status_code != 500
    assert "success" in body


# ── 11. Flutter camera multipart content type accepted ───────────────────────

def test_predict_jpeg_with_octet_stream_content_type_accepted():
    """
    Flutter camera uploads may arrive as application/octet-stream even when the
    filename is .jpg. The backend should decode bytes instead of rejecting early.
    """
    jpeg = _make_jpeg_bytes()
    r = client.post(
        "/api/v1/predict",
        files={"image": ("CAP_test.jpg", jpeg, "application/octet-stream")},
    )
    body = r.json()

    assert r.status_code != 415
    assert body["status"] != "VALIDATION_ERROR"
    assert body["success"] is False
    assert body["status"] in ("MODEL_NOT_READY", "IMAGE_QUALITY_FAILED")


# ── 12. Validation decode fallback ───────────────────────────────────────────

def test_validation_falls_back_to_opencv_when_pillow_fails(monkeypatch):
    """
    Dataset verification found malformed PNG ancillary chunks that can break
    Pillow while OpenCV still decodes image pixels. Keep that fallback covered.
    """
    jpeg = _make_jpeg_bytes()

    def _raise_decode_error(*args, **kwargs):
        raise OSError("simulated Pillow decode failure")

    monkeypatch.setattr(validation.Image, "open", _raise_decode_error)

    image_rgb = validation.validate_upload(
        filename="eye.jpg",
        content_type="image/jpeg",
        data=jpeg,
    )

    assert image_rgb.shape == (300, 300, 3)
    assert image_rgb.dtype == np.uint8


# ── 13. Info endpoint ─────────────────────────────────────────────────────────

def test_info_endpoint():
    r = client.get("/api/v1/info")
    assert r.status_code == 200
    body = r.json()
    assert "application" in body
    assert "api_version" in body
    assert "model_name" in body
    assert "model_available" in body
    assert "disclaimer" in body
    assert "research" in body["disclaimer"].lower()
