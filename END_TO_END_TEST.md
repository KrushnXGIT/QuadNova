# End-To-End Test Record

Date: 2026-08-22

## Components

- Flutter app: `app/`
- Backend: `backend/`
- AI model: `ai_model/`
- Predictor: `ai_model/src/inference/predictor.py::AnaemiaPredictor`
- Checkpoint: `ai_model/models/hb_regressor_best.pt`

## Commands Run

AI tests:

```cmd
cd ai_model
..\backend\.venv\Scripts\python.exe -m pytest tests -q
```

Result:

```text
129 passed, 14 subtests passed in 8.91s
```

Backend tests:

```cmd
cd backend
.venv\Scripts\python.exe -m pytest tests -q
```

Result:

```text
13 passed in 0.81s
```

Backend startup:

```cmd
cd backend
.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Observed model load time:

```text
AI model loaded in 3.283s
```

Health:

```cmd
curl.exe -s http://127.0.0.1:8000/health
```

Result:

```json
{"status":"ok","service":"anaemia-screening-backend"}
```

Model status:

```cmd
curl.exe -s http://127.0.0.1:8000/api/v1/model/status
```

Result: `ready=true`, `status=MODEL_READY`,
`model.version=anaemia-hb-mobilenetv3-v1`.

Prediction with real image and matching ROI mask:

```cmd
curl.exe -s -F image=@data\raw\sample_dataset\20200118_164733.jpg -F mask=@data\raw\sample_dataset\20200118_164733_forniceal_palpebral.png http://127.0.0.1:8000/api/v1/predict
```

Result:

```json
{
  "success": true,
  "status": "PREDICTION_COMPLETE",
  "data": {
    "estimated_hb_g_dl": 6.371901512145996,
    "hb_std_g_dl": 0.6761209964752197,
    "confidence_interval_95": [5.05, 7.7],
    "confidence_status": "MEDIUM_CONFIDENCE",
    "image_quality": {
      "status": "GOOD",
      "score": 0.8243265262401682,
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
  },
  "meta": {
    "inference_seconds": 1.9021
  }
}
```

Prediction with image only:

```cmd
curl.exe -s -F image=@data\raw\sample_dataset\20200118_164733.jpg http://127.0.0.1:8000/api/v1/predict
```

Result:

```json
{"success":false,"status":"ROI_FAILED","data":{"retry":true,"message":"A valid conjunctiva ROI mask is required for prediction."}}
```

## Flutter Status

Flutter API parsing was updated for the real AI response fields:

- `estimated_hb_g_dl`
- `hb_std_g_dl`
- `confidence_interval_95`
- `confidence_status`
- `image_quality`
- `ROI_FAILED`

`flutter analyze` was attempted but hung with no output for more than 90 seconds
in this environment and was stopped. `flutter test` was attempted but also hung
with no output for more than 60 seconds and was stopped. Flutter device
end-to-end remains blocked for successful prediction because the current camera
flow sends only `image`, not the required ROI `mask`.

## Known Limitation

The existing AI model requires a valid conjunctiva ROI mask for successful Hb
prediction. Phone camera-only uploads correctly return `ROI_FAILED`; no mock or
fake Hb value is returned.

The uncertainty fields use the model's MC-dropout style sampling, so
`hb_std_g_dl` and `confidence_interval_95` may vary slightly between runs.
