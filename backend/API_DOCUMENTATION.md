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
- `mask`: optional ROI mask file. If omitted, the backend automatically
  generates a conjunctiva ROI mask from the uploaded image using classical CV
  heuristics (`app/services/mask_generator.py`, controlled by the
  `AUTO_MASK_ENABLED` setting). This is what makes live phone-camera captures
  work. Explicitly supplied masks are still subject to the same image-domain
  gate and cannot bypass content validation. If detection finds no plausible
  eye context, the endpoint returns `ROI_FAILED` with
  `error.code=CONJUNCTIVA_NOT_DETECTED` before the predictor is called.

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

HTTP status mapping: `200` for PREDICTION_COMPLETE / LOW_CONFIDENCE,
`422` for IMAGE_QUALITY_FAILED / ROI_FAILED, `503` for MODEL_NOT_READY,
`500` for INFERENCE_ERROR / INTERNAL_ERROR, `400`/`413`/`415` for
VALIDATION_ERROR variants.

Failure statuses:

- `VALIDATION_ERROR`
- `EYE_NOT_DETECTED`: no eye or close-up eye context could be localized
- `CONJUNCTIVA_NOT_DETECTED`: no valid conjunctiva candidate was found inside the eye crop
- `ROI_QUALITY_FAILED`: the validated conjunctiva ROI failed technical quality checks
- `IMAGE_QUALITY_FAILED`
- `ROI_FAILED`
- `MODEL_NOT_READY`
- `INFERENCE_ERROR`
- `INTERNAL_ERROR`

## Development debug visualization

Set `HEMOSCAN_DEBUG_DIR` before starting the backend to write validation-only
artifacts for the next request: original image, eye bounding-box overlay, eye
crop, conjunctiva overlay, final ROI, and `validation.json`. The directory is
disabled by default and must not be enabled for normal clinical use.

Conjunctiva detection failure example:

```json
{
  "success": false,
  "status": "ROI_FAILED",
  "error": {
    "code": "CONJUNCTIVA_NOT_DETECTED",
    "message": "No valid conjunctiva region could be detected.",
    "retryable": true
  },
  "validation": {
    "roi_detected": false,
    "quality_status": "not_run"
  },
  "data": {
    "retry": true,
    "message": "Conjunctiva not detected. Please position the inner eyelid correctly and capture the image again."
  }
}
```

`IMAGE_QUALITY_FAILED` is returned for blur, exposure, or resolution failures.
Neither failure response contains `estimated_hb_g_dl`. The quality thresholds
remain prototype heuristics inherited from the existing CV pipeline and must be
validated against a representative deployment dataset before clinical use.

The backend must not expose tracebacks, local absolute paths, or fabricated Hb
values.
