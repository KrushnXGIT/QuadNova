# ai_model

This package exposes the backend-facing screening model without embedding FastAPI.

## Usage

```python
from ai_model.predictor import AnaemiaPredictor

predictor = AnaemiaPredictor(model_path="models/hb_regressor_best.pt")
predictor.load()
result = predictor.predict(image, mask_path="path/to/mask.png")
```

The result is JSON-serializable and suitable for later API response wrapping.
