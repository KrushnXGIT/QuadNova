# Backend Model Integration Guide

This project is intentionally prepared as a backend-ready inference module without building FastAPI itself.

## Python import

```python
from src.inference.predictor import AnaemiaPredictor

predictor = AnaemiaPredictor(
    model_path="models/hb_regressor_best.pt",
    device="cpu",
)

predictor.load()
result = predictor.predict(image, mask_path="data/raw/example_forniceal_palpebral.png")
```

## Minimal backend usage

```python
from src.inference.predictor import AnaemiaPredictor

predictor = AnaemiaPredictor(model_path="models/hb_regressor_best.pt")
predictor.load()

result = predictor.predict(image)
return result
```

## Notes

- The backend does not need to know the internals of MobileNetV3-small.
- The backend does not need to reimplement ROI extraction or preprocessing.
- The backend should call the model through the single `AnaemiaPredictor` API.
- Prediction outputs are JSON-serializable dictionaries.
- If the image is low quality or the ROI cannot be extracted, the predictor returns structured failure states instead of raising raw exceptions.

## Production behavior

- Use `load()` once at startup.
- Reuse the same predictor instance for multiple requests.
- Keep the checkpoint path fixed unless a model update is intentionally deployed.
- Treat the output as a screening estimate, not a clinical diagnostic result.
