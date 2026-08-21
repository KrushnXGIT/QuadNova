# Backend API Documentation

Base URL: `http://<host>:8000`

## GET /health

Returns liveness status.

```json
{
  "status": "ok",
  "service": "anaemia-screening-backend"
}
```

## GET /api/v1/model/status

Returns actual AI model readiness.

```json
{
  "ready": true,
  "available": true,
  "status": "MODEL_READY",
  "model": {
    "name": "MobileNetV3-small",
    "version": "anaemia-hb-mobilenetv3-v1",
    "checkpoint": "../ai_model/models/hb_regressor_best.pt"
  }
}
```

## POST /api/v1/predict

Request type: `multipart/form-data`

Fields:

- `image`: required image file
- `mask`: optional ROI mask file; required by the current AI predictor for a
  successful Hb estimate

Successful response:

```json
{
  "success": true,
  "status": "PREDICTION_COMPLETE",
  "data": {
    "estimated_hb_g_dl": 6.37,
    "hb_std_g_dl": 0.85,
    "confidence_interval_95": [4.7, 8.05],
    "confidence_status": "MEDIUM_CONFIDENCE",
    "image_quality": {
      "status": "GOOD",
      "score": 0.82,
      "failure_reasons": []
    },
    "roi": {
      "status": "VALID"
    },
    "recommendation": "Screening estimate only. Consider confirmatory testing when appropriate.",
    "model": {
      "name": "MobileNetV3-small",
      "version": "anaemia-hb-mobilenetv3-v1"
    }
  }
}
```

Failure statuses:

- `VALIDATION_ERROR`
- `IMAGE_QUALITY_FAILED`
- `ROI_FAILED`
- `MODEL_NOT_READY`
- `INFERENCE_ERROR`

The backend must not expose tracebacks, local absolute paths, or fabricated Hb
values.
