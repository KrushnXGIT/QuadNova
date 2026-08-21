# Model API Contract

This is the planned boundary between the backend and the model. It does not
implement inference.

## Input

- RGB image tensor produced by the backend preprocessing pipeline
- Expected spatial size: 224 x 224, subject to confirmation from training
- Normalization: must be confirmed from the training configuration

## Output

- `estimated_hb`: numeric haemoglobin estimate in g/dL
- `confidence`: numeric value from 0.0 to 1.0 with a documented derivation
- model name and version metadata

## Required evidence before integration

- Loadable checkpoint and framework/runtime requirements
- Predictor entry point
- Exact preprocessing and output-shape documentation
- Confidence or uncertainty methodology
- Held-out evaluation results
