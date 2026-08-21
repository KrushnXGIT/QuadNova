"""Regression metrics and evaluation plots for Phase 4."""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


def regression_metrics(actual, predicted):
    actual = np.asarray(actual, dtype=np.float64)
    predicted = np.asarray(predicted, dtype=np.float64)
    if actual.size == 0 or actual.shape != predicted.shape:
        raise ValueError("actual and predicted must be non-empty arrays of equal shape")
    errors = predicted - actual
    ss_res = float(np.sum(errors ** 2))
    ss_tot = float(np.sum((actual - actual.mean()) ** 2))
    return {
        "MAE": float(np.mean(np.abs(errors))),
        "RMSE": float(np.sqrt(np.mean(errors ** 2))),
        "R2": float(1.0 - ss_res / ss_tot) if ss_tot else float("nan"),
    }


def mean_baseline_metrics(train_targets, actual):
    baseline = float(np.mean(train_targets))
    return {"prediction": baseline, **regression_metrics(actual, np.full(len(actual), baseline))}


def save_evaluation_plots(history, actual, predicted, output_dir):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    plt.figure()
    plt.plot(history["train_loss"], label="train")
    plt.plot(history["val_loss"], label="validation")
    plt.xlabel("Epoch")
    plt.ylabel("MSE loss")
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_dir / "training_validation_loss.png", dpi=150)
    plt.close()

    errors = np.asarray(predicted) - np.asarray(actual)
    plt.figure()
    plt.scatter(actual, predicted)
    bounds = [min(np.min(actual), np.min(predicted)), max(np.max(actual), np.max(predicted))]
    plt.plot(bounds, bounds, linestyle="--")
    plt.xlabel("Actual Hb (g/dL)")
    plt.ylabel("Predicted Hb (g/dL)")
    plt.tight_layout()
    plt.savefig(output_dir / "predicted_vs_actual.png", dpi=150)
    plt.close()

    plt.figure()
    plt.hist(errors, bins=min(20, max(1, len(errors))))
    plt.xlabel("Prediction error (g/dL)")
    plt.ylabel("Count")
    plt.tight_layout()
    plt.savefig(output_dir / "residual_distribution.png", dpi=150)
    plt.close()
