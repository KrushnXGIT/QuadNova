# Backend Integration

The Phase 4 model can be integrated into another system because the model
contract is small and explicit:

```text
raw image + combined ROI mask
    -> src.vision.pipeline.process_subject()
    -> roi_tensor: float32, shape (224, 224, 3), RGB
    -> HbRegressor
    -> one continuous Hb value in g/dL
```

## Existing checkpoint

```text
models/hb_regressor_best.pt
```

It contains `model_state_dict` and the input configuration. The target system
must use the same MobileNetV3-small architecture, 224x224 input, combined
conjunctiva ROI, CLAHE normalization, and quality override used by
`src.model.predict`.

## Local or service backend

Any Python service can load the model once at process startup and call:

```python
from src.model.predict import predict

response = predict(
    raw_path="subject.jpg",
    mask_path="subject_forniceal_palpebral.png",
    model_path="models/hb_regressor_best.pt",
    subject_id="subject",
    device="cpu",
)
```

The response includes `quality_status`, `quality_report`, and
`estimated_hb_g_dl` only when the image is accepted and the checkpoint loads.
The current project does not implement an API, authentication, storage, or
deployment layer.

## Hardware

CPU inference is supported. CUDA inference is available when the installed
PyTorch build and GPU support it:

```powershell
python -m src.model.predict --image subject.jpg --mask subject_forniceal_palpebral.png --model models/hb_regressor_best.pt --subject-id subject --device cuda
```

The command rejects `cuda` when CUDA is unavailable instead of silently using
another device.

## Mobile or non-Python backend

The PyTorch checkpoint can later be converted to an agreed runtime such as
TorchScript, ONNX, or a mobile-specific format. Conversion must preserve the
preprocessing contract and should be validated against the reference Python
inference output on the same images. This is a future integration step, not a
claim that the current model is clinically validated or deployment-ready.

## Important limitation

The promoted pretrained CNN test MAE is 2.0454 g/dL versus 1.9324 g/dL for
the mean-Hb baseline. A different backend changes hosting, not model quality.
Phase 5 should evaluate robustness and model improvements before any
user-facing deployment.