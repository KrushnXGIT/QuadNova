import numpy as np
from PIL import Image

from src.inference.predictor import AnaemiaPredictor


def _make_valid_fixture(tmp_path, name="synthetic"):
    raw = np.random.default_rng(0).integers(0, 255, size=(224, 224, 3), dtype=np.uint8)
    raw_path = tmp_path / f"{name}.jpg"
    Image.fromarray(raw, mode="RGB").save(raw_path)

    mask = np.zeros((224, 224, 4), dtype=np.uint8)
    yy, xx = np.ogrid[:224, :224]
    circle = (yy - 112) ** 2 + (xx - 112) ** 2 <= 80 ** 2
    mask[circle] = [40, 80, 120, 255]
    mask_path = tmp_path / f"{name}_forniceal_palpebral.png"
    Image.fromarray(mask, mode="RGBA").save(mask_path)
    return raw_path, mask_path


def test_model_loads():
    predictor = AnaemiaPredictor(model_path="models/hb_regressor_best.pt")
    assert predictor.load() is True
    assert predictor.is_ready() is True
    info = predictor.get_model_info()
    assert info["name"] == "MobileNetV3-small"


def test_valid_image_prediction(tmp_path):
    raw_path, mask_path = _make_valid_fixture(tmp_path, name="valid")
    predictor = AnaemiaPredictor(model_path="models/hb_regressor_best.pt")
    assert predictor.load() is True
    result = predictor.predict(str(raw_path), mask_path=str(mask_path), subject_id="valid")
    assert result["success"] is True
    assert result["status"] == "PREDICTION_COMPLETE"
    data = result["data"]
    assert isinstance(data["estimated_hb_g_dl"], float)
    assert isinstance(data["hb_std_g_dl"], float)
    assert len(data["confidence_interval_95"]) == 2
    assert data["confidence_status"] in {"HIGH_CONFIDENCE", "MEDIUM_CONFIDENCE", "LOW_CONFIDENCE"}
    assert data["model"]["version"] == "anaemia-hb-mobilenetv3-v1"


def test_invalid_image_returns_structured_failure():
    predictor = AnaemiaPredictor(model_path="models/hb_regressor_best.pt")
    assert predictor.load() is True
    bad = np.zeros((12, 12, 1), dtype=np.uint8)
    result = predictor.predict(bad)
    assert result["success"] is False
    assert result["status"] == "IMAGE_QUALITY_FAILED"
    assert result["data"]["retry"] is True


def test_poor_quality_image_is_rejected(tmp_path):
    predictor = AnaemiaPredictor(model_path="models/hb_regressor_best.pt")
    assert predictor.load() is True
    poor = np.zeros((224, 224, 3), dtype=np.uint8)
    result = predictor.predict(poor)
    assert result["success"] is False
    assert result["status"] == "IMAGE_QUALITY_FAILED"


def test_roi_failure_returns_retry_payload(tmp_path):
    raw_path, _ = _make_valid_fixture(tmp_path, name="roi_fail")
    predictor = AnaemiaPredictor(model_path="models/hb_regressor_best.pt")
    assert predictor.load() is True

    bad_mask = tmp_path / "bad_mask.png"
    Image.fromarray(np.zeros((224, 224, 4), dtype=np.uint8), mode="RGBA").save(bad_mask)
    result = predictor.predict(str(raw_path), mask_path=str(bad_mask), subject_id="roi_fail")
    assert result["success"] is False
    assert result["status"] == "ROI_FAILED"
    assert result["data"]["retry"] is True


def test_model_unavailable_returns_model_not_ready(tmp_path):
    predictor = AnaemiaPredictor(model_path=tmp_path / "no_model.pt")
    assert predictor.load() is False
    result = predictor.predict(np.zeros((224, 224, 3), dtype=np.uint8))
    assert result["success"] is False
    assert result["status"] == "MODEL_NOT_READY"


def test_output_schema_is_json_serializable(tmp_path):
    raw_path, mask_path = _make_valid_fixture(tmp_path, name="schema")
    predictor = AnaemiaPredictor(model_path="models/hb_regressor_best.pt")
    assert predictor.load() is True
    result = predictor.predict(str(raw_path), mask_path=str(mask_path), subject_id="schema")
    assert result["success"] is True
    assert set(result.keys()) == {"success", "status", "data"}
    assert isinstance(result["data"]["image_quality"]["score"], float)
    assert isinstance(result["data"]["roi"]["status"], str)
    assert isinstance(result["data"]["model"]["version"], str)


def test_numeric_types_and_uncertainty_fields(tmp_path):
    raw_path, mask_path = _make_valid_fixture(tmp_path, name="numeric")
    predictor = AnaemiaPredictor(model_path="models/hb_regressor_best.pt")
    assert predictor.load() is True
    result = predictor.predict(str(raw_path), mask_path=str(mask_path), subject_id="numeric")
    data = result["data"]
    assert isinstance(data["estimated_hb_g_dl"], float)
    assert isinstance(data["hb_std_g_dl"], float)
    assert isinstance(data["confidence_interval_95"][0], float)
    assert isinstance(data["confidence_interval_95"][1], float)
    assert data["hb_std_g_dl"] >= 0.0


def test_confidence_status_is_reported(tmp_path):
    raw_path, mask_path = _make_valid_fixture(tmp_path, name="confidence")
    predictor = AnaemiaPredictor(model_path="models/hb_regressor_best.pt")
    assert predictor.load() is True
    result = predictor.predict(str(raw_path), mask_path=str(mask_path), subject_id="confidence")
    assert result["data"]["confidence_status"] in {"HIGH_CONFIDENCE", "MEDIUM_CONFIDENCE", "LOW_CONFIDENCE"}


def test_checkpoint_reload_succeeds(tmp_path):
    raw_path, mask_path = _make_valid_fixture(tmp_path, name="reload")
    predictor = AnaemiaPredictor(model_path="models/hb_regressor_best.pt")
    assert predictor.load() is True
    reloaded = AnaemiaPredictor(model_path="models/hb_regressor_best.pt")
    assert reloaded.load() is True
    result = reloaded.predict(str(raw_path), mask_path=str(mask_path), subject_id="reload")
    assert result["success"] is True


def test_no_fake_hb_prediction(tmp_path):
    raw_path, mask_path = _make_valid_fixture(tmp_path, name="fake_guard")
    predictor = AnaemiaPredictor(model_path="models/hb_regressor_best.pt")
    assert predictor.load() is True
    result = predictor.predict(str(raw_path), mask_path=str(mask_path), subject_id="fake_guard")
    hb = result["data"]["estimated_hb_g_dl"]
    assert 0.0 <= hb <= 30.0
    assert hb != 10.8
