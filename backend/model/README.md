# Model Directory

Place the trained MobileNetV3-small Hb regression model checkpoint here.

## Expected filename

```
mobilenetv3_hb.pt        # PyTorch checkpoint  — OR —
mobilenetv3_hb.h5        # Keras/TF checkpoint
```

## Configure

After placing the file, update `backend/.env`:

```env
MODEL_PATH=C:/Users/HP/Desktop/wrk/smartphone-anaemia-screening/backend/model/mobilenetv3_hb.pt
MODEL_ENABLED=true
```

Then restart the backend:

```powershell
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Integration Checklist

- [ ] Implement `_load_real_model()` in `app/models/model_adapter.py`
- [ ] Implement `_run_inference()` in `app/models/model_adapter.py`
- [ ] Confirm preprocessing matches training pipeline (`src/vision/`)
- [ ] Confirm normalization (ImageNet mean/std or custom)
- [ ] Confirm model output shape (single float for Hb regression)
- [ ] Confirm confidence mechanism (MC-Dropout / ensemble / direct output)
- [ ] Set `MODEL_ENABLED=true` and `MODEL_PATH` in `.env`
- [ ] Restart server and verify `/api/v1/model/status` shows `available: true`

## While model is absent

All `/api/v1/predict` requests will return:

```json
{
  "success": false,
  "status": "MODEL_NOT_READY",
  "message": "The AI screening model is not currently available."
}
```

**No fake Hb values are ever generated.**
