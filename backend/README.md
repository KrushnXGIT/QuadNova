# FastAPI Backend

Backend for the Flutter -> FastAPI -> existing AI model flow.

## AI Integration

The backend uses the existing AI project in `../ai_model/`.

- Predictor entry point: `ai_model/src/inference/predictor.py::AnaemiaPredictor`
- Checkpoint: `../ai_model/models/hb_regressor_best.pt`
- Model version: `anaemia-hb-mobilenetv3-v1`

The backend does not duplicate ROI extraction, preprocessing, normalization,
Hb regression, uncertainty, or confidence logic.

## Setup

```cmd
cd backend
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Configure `backend/.env`:

```env
AI_MODEL_PATH=../ai_model/models/hb_regressor_best.pt
AI_DEVICE=cpu
HOST=0.0.0.0
PORT=8000
```

## Run

```cmd
cd backend
.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

For a physical Android device, use the PC LAN IP in the Flutter server settings,
for example `http://192.168.5.109:8000`.

## Test

```cmd
cd ai_model
..\backend\.venv\Scripts\python.exe -m pytest tests -q

cd ..\backend
.venv\Scripts\python.exe -m pytest tests -q
```

## Current Limitation

The current AI model contract requires a conjunctiva ROI mask for successful
prediction. `POST /api/v1/predict` accepts an optional `mask` file field. If the
Flutter camera sends only an image, the backend returns `ROI_FAILED` rather than
fabricating a haemoglobin estimate.
