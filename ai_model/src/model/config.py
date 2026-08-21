"""Reproducible Phase 4 model configuration."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODEL_DIR = PROJECT_ROOT / "models"
RESULTS_DIR = PROJECT_ROOT / "results"
SPLIT_PATH = PROJECT_ROOT / "data" / "splits" / "split.json"
INPUT_SIZE = (224, 224)
BATCH_SIZE = 8
LEARNING_RATE = 1e-4
MAX_EPOCHS = 30
PATIENCE = 5
RANDOM_SEED = 42
NORM_METHOD = "clahe"
# Real-dataset calibration: the inherited 50.0 blur heuristic rejected
# 153/196 raw images; 10.0 retains all images in the verified set and remains
# a quality gate. This override is model-training specific; CV defaults stay
# unchanged until broader deployment data is available.
QUALITY_OVERRIDES = {"blur_threshold": 10.0}
MODEL_NAME = "mobilenet_v3_small"
LOSS_NAME = "MSELoss"
