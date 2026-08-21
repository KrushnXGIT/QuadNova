# Backend Model Integration

## Current status

The backend already exposes a model adapter boundary at
`backend/app/models/model_adapter.py`, but the real model loader and inference
methods are intentionally unimplemented. The backend currently reports
`MODEL_NOT_READY` and never fabricates an Hb value.

## Missing artifacts

- `models/hb_regressor_best.pt` or another validated checkpoint
- Model framework dependency list
- Predictor implementation
- Real conjunctiva ROI implementation
- Training-compatible normalization
- Confidence/uncertainty implementation
- Inference-path tests

## Integration sequence

1. Supply and verify the checkpoint and model provenance.
2. Document the training preprocessing and output contract.
3. Implement the adapter loader and predictor in the backend boundary.
4. Validate against held-out examples and add regression tests.
5. Enable the model only after the readiness and inference checks pass.
