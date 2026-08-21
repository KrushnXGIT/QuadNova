# Model API Contract

This document defines the exact contract that the future FastAPI backend will call.

## Initialization

```python
from src.inference.predictor import AnaemiaPredictor

predictor = AnaemiaPredictor(
    model_path="models/hb_regressor_best.pt",
    mask_path=None,
    device="cpu",
)
predictor.load()
```

## Prediction calls

```python
result = predictor.predict(image)
# or
result = predictor.predict_from_path("data/raw/example.jpg", mask_path="data/raw/example_forniceal_palpebral.png")
```

## Supported input

- `image`: a NumPy array, PIL image, or filesystem path to an image file
- `mask_path`: optional path to the conjunctiva ROI mask; required when operating on the full CV pipeline
- `subject_id`: optional identifier for logs and debugging

## Output contract

The model returns a JSON-serializable dictionary with:

```python
{
    "success": True,
    "status": "PREDICTION_COMPLETE",
    "data": {
        "estimated_hb_g_dl": 11.4,
        "hb_std_g_dl": 0.6,
        "confidence_interval_95": [10.2, 12.6],
        "confidence_status": "MEDIUM_CONFIDENCE",
        "image_quality": {
            "status": "GOOD",
            "score": 0.91,
            "failure_reasons": []
        },
        "roi": {"status": "VALID"},
        "recommendation": "Screening estimate only. Consider confirmatory testing when appropriate.",
        "model": {
            "name": "MobileNetV3-small",
            "version": "anaemia-hb-mobilenetv3-v1"
        }
    }
}
```

## Failure states

- `IMAGE_QUALITY_FAILED`: image is too blurry, too dark, too bright, or otherwise not usable
- `ROI_FAILED`: ROI detection failed or the mask is missing/invalid
- `MODEL_NOT_READY`: checkpoint missing, unreadable, or incompatible
- `INFERENCE_ERROR`: a runtime inference or preprocessing failure

## Model status

- `predictor.load() -> bool`
- `predictor.is_ready() -> bool`
- `predictor.get_model_info() -> dict`

## Model version

The current model version is `anaemia-hb-mobilenetv3-v1`.

## Preprocessing requirements

- Input image is RGB
- EXIF-orientation correction is applied when loading
- Image-quality checks are performed before ROI extraction
- ROI extraction uses the existing conjunctiva mask pipeline
- ROI is normalized and resized to 224x224
- Model input is channel-first float32 tensor with 3 channels

## Engineering note

The model is a screening prototype and not clinically validated. The backend should treat all output as provisional screening estimates only.
