"""
phase_j_deployment.py
=====================
PHASE J: Deployment Readiness Check

Checks:
  - Checkpoint loading
  - CPU inference
  - Inference latency (mean over 10 runs)
  - Model size on disk
  - TorchScript compatibility
  - ONNX export (if onnx is installed)

Produces:
  MODEL_DEPLOYMENT.md
"""

import json
import sys
import time
from pathlib import Path

import numpy as np
import torch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.model.config import MODEL_DIR
from src.model.model import HbRegressor


def run_deployment_check(
    model_path: str = None,
    output_dir: str = None,
    n_latency_runs: int = 10,
):
    model_path = Path(model_path or MODEL_DIR / "hb_regressor_best.pt")
    output_dir = Path(output_dir or PROJECT_ROOT)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=== PHASE J: Deployment Readiness ===")
    results = {}

    # ------------------------------------------------------------------ #
    # 1. Checkpoint loading
    # ------------------------------------------------------------------ #
    try:
        checkpoint = torch.load(model_path, map_location="cpu", weights_only=False)
        config = checkpoint.get("config", {})
        model = HbRegressor(
            pretrained=config.get("pretrained", False),
            freeze_backbone=config.get("freeze_backbone", False),
        )
        model.load_state_dict(checkpoint["model_state_dict"])
        model.eval()
        results["checkpoint_loading"] = "PASS"
        print("  ✓ Checkpoint loading: PASS")
    except Exception as e:
        results["checkpoint_loading"] = f"FAIL: {e}"
        print(f"  ✗ Checkpoint loading: FAIL — {e}")
        return results

    target_mean = config.get("target_mean", 0.0)
    target_std = config.get("target_std", 1.0)

    # ------------------------------------------------------------------ #
    # 2. CPU inference
    # ------------------------------------------------------------------ #
    dummy = torch.zeros(1, 3, 224, 224)
    try:
        with torch.no_grad():
            out = model(dummy)
        assert out.shape == (1,), f"Expected (1,) got {out.shape}"
        results["cpu_inference"] = "PASS"
        print("  ✓ CPU inference: PASS")
    except Exception as e:
        results["cpu_inference"] = f"FAIL: {e}"
        print(f"  ✗ CPU inference: FAIL — {e}")

    # ------------------------------------------------------------------ #
    # 3. Inference latency (mean over n_latency_runs)
    # ------------------------------------------------------------------ #
    latencies = []
    try:
        for _ in range(n_latency_runs):
            t0 = time.perf_counter()
            with torch.no_grad():
                _ = model(dummy)
            latencies.append((time.perf_counter() - t0) * 1000)
        mean_ms = float(np.mean(latencies))
        std_ms = float(np.std(latencies))
        results["inference_latency_ms"] = {"mean": mean_ms, "std": std_ms, "n": n_latency_runs}
        print(f"  ✓ Inference latency: {mean_ms:.1f} ± {std_ms:.1f} ms (n={n_latency_runs})")
    except Exception as e:
        results["inference_latency_ms"] = f"FAIL: {e}"
        print(f"  ✗ Latency measurement: FAIL — {e}")

    # ------------------------------------------------------------------ #
    # 4. Model size on disk
    # ------------------------------------------------------------------ #
    import os
    size_bytes = os.path.getsize(model_path)
    size_mb = size_bytes / (1024 * 1024)
    results["model_size_mb"] = round(size_mb, 3)
    results["model_size_bytes"] = size_bytes
    print(f"  ✓ Model size: {size_mb:.2f} MB")

    # Parameter count
    n_params = sum(p.numel() for p in model.parameters())
    n_trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    results["total_parameters"] = n_params
    results["trainable_parameters"] = n_trainable
    print(f"  ✓ Parameters: {n_params:,} total, {n_trainable:,} trainable")

    # ------------------------------------------------------------------ #
    # 5. TorchScript compatibility
    # ------------------------------------------------------------------ #
    try:
        scripted = torch.jit.trace(model, dummy)
        ts_out = scripted(dummy)
        assert ts_out.shape == (1,)
        ts_path = model_path.parent / "hb_regressor_best_scripted.pt"
        scripted.save(str(ts_path))
        results["torchscript"] = {"status": "PASS", "path": str(ts_path)}
        print(f"  ✓ TorchScript: PASS → {ts_path}")
    except Exception as e:
        results["torchscript"] = {"status": f"FAIL: {e}"}
        print(f"  ✗ TorchScript: FAIL — {e}")

    # ------------------------------------------------------------------ #
    # 6. ONNX export
    # ------------------------------------------------------------------ #
    try:
        import onnx  # type: ignore
        onnx_path = model_path.parent / "hb_regressor_best.onnx"
        torch.onnx.export(
            model,
            dummy,
            str(onnx_path),
            input_names=["roi_image"],
            output_names=["hb_estimate"],
            dynamic_axes={"roi_image": {0: "batch_size"}},
            opset_version=11,
        )
        onnx_model = onnx.load(str(onnx_path))
        onnx.checker.check_model(onnx_model)
        onnx_size_mb = os.path.getsize(onnx_path) / (1024 * 1024)
        results["onnx"] = {"status": "PASS", "path": str(onnx_path), "size_mb": round(onnx_size_mb, 3)}
        print(f"  ✓ ONNX export: PASS → {onnx_path} ({onnx_size_mb:.2f} MB)")
    except ImportError:
        results["onnx"] = {"status": "SKIPPED — onnx not installed"}
        print("  ℹ ONNX: SKIPPED — onnx package not installed")
    except Exception as e:
        results["onnx"] = {"status": f"FAIL: {e}"}
        print(f"  ✗ ONNX: FAIL — {e}")

    # Save results JSON
    (output_dir / "deployment_check.json").write_text(
        json.dumps(results, indent=2, default=str), encoding="utf-8"
    )

    # Write MODEL_DEPLOYMENT.md
    _write_deployment_md(results, model_path, output_dir, target_mean, target_std, config)
    return results


def _write_deployment_md(results, model_path, output_dir, target_mean, target_std, config):
    lat = results.get("inference_latency_ms", {})
    ts = results.get("torchscript", {})
    onnx = results.get("onnx", {})

    lines = [
        "# Model Deployment Guide",
        "",
        "## Overview",
        "",
        "This document describes how to use the Hb screening model checkpoint in a backend service.",
        "The backend should call `predict_with_confidence(image_path, mask_path, model_path)` and",
        "receive a fully structured result.",
        "",
        "---",
        "",
        "## Model Information",
        "",
        "| Property | Value |",
        "|----------|-------|",
        f"| Architecture | MobileNetV3-small |",
        f"| Checkpoint | `{model_path}` |",
        f"| Size on disk | {results.get('model_size_mb', 'N/A')} MB |",
        f"| Total parameters | {results.get('total_parameters', 'N/A'):,} |" if isinstance(results.get('total_parameters'), int) else f"| Total parameters | N/A |",
        f"| Target mean (for denormalization) | {target_mean:.4f} |",
        f"| Target std (for denormalization) | {target_std:.4f} |",
        f"| Normalization method | {config.get('norm_method', 'clahe')} |",
        f"| Input size | 224 × 224 × 3 |",
        "",
        "---",
        "",
        "## Deployment Readiness Checks",
        "",
        "| Check | Status |",
        "|-------|--------|",
        f"| Checkpoint loading | {results.get('checkpoint_loading', 'N/A')} |",
        f"| CPU inference | {results.get('cpu_inference', 'N/A')} |",
        f"| Mean CPU latency | {lat.get('mean', 'N/A'):.1f} ms (n={lat.get('n', 0)})" if isinstance(lat, dict) else f"| Mean CPU latency | {lat} |",
        f"| TorchScript | {ts.get('status', 'N/A')} |",
        f"| ONNX | {onnx.get('status', 'N/A')} |",
        "",
        "---",
        "",
        "## Backend Integration",
        "",
        "The backend should NOT be integrated yet. The AI pipeline must be confirmed stable first.",
        "",
        "When ready, the backend can call:",
        "",
        "```python",
        "from src.model.predict import predict_with_confidence",
        "",
        "result = predict_with_confidence(",
        "    raw_path='path/to/image.jpg',",
        "    mask_path='path/to/mask.png',",
        "    model_path='models/hb_regressor_best.pt',",
        "    subject_id='user_123',",
        "    device='cpu',",
        "    mc_samples=25,",
        ")",
        "```",
        "",
        "### Output Schema",
        "",
        "```json",
        "{",
        '  "estimated_hb_g_dl": 11.5,',
        '  "hb_std_g_dl": 0.42,',
        '  "confidence_interval_95": [10.7, 12.3],',
        '  "confidence_status": "MEDIUM_CONFIDENCE",',
        '  "image_quality_status": "ACCEPTED",',
        '  "image_quality_score": 0.81,',
        '  "image_failure_reasons": [],',
        '  "recommendation": "SCREENING_ESTIMATE_LOW_CONFIDENCE",',
        '  "recommendation_text": "...",',
        '  "model_version": "hb_regressor_v1.0_mobilenetv3small",',
        '  "_disclaimer": "AI-based anaemia screening prototype. Not a diagnosis."',
        "}",
        "```",
        "",
        "---",
        "",
        "## Medical Safety Requirements",
        "",
        "The backend MUST display these messages to users:",
        "",
        "- `estimated_hb_g_dl`: Displayed as **'Estimated Hb: X.X g/dL (screening estimate)'**",
        "- `recommendation: RETAKE_IMAGE` → **'Please retake the image'**",
        "- `recommendation: CONFIRMATORY_TEST_RECOMMENDED` → **'Confirmatory blood test recommended'**",
        "- `confidence_status: LOW_CONFIDENCE` → Display with warning indicator",
        "",
        "The backend MUST NOT:",
        "- Present the Hb estimate as a clinical diagnosis",
        "- Hide the uncertainty / confidence status from the user",
        "- Make clinical decisions based solely on the Hb estimate",
        "",
        "---",
        "",
        "## TorchScript Deployment",
        "",
    ]
    if ts.get("status") == "PASS":
        lines += [
            f"The model has been exported to TorchScript: `{ts.get('path')}`",
            "",
            "```python",
            "import torch",
            "model = torch.jit.load('models/hb_regressor_best_scripted.pt')",
            "model.eval()",
            "output = model(image_tensor)  # (1, 3, 224, 224) float32",
            "# Denormalize: hb = output * target_std + target_mean",
            "```",
        ]
    else:
        lines.append(f"TorchScript status: {ts.get('status', 'not checked')}")

    lines += [
        "",
        "---",
        "",
        "*This is a pre-deployment readiness check. Backend integration should only proceed after clinical validation.*",
    ]

    (output_dir / "MODEL_DEPLOYMENT.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Saved: {output_dir / 'MODEL_DEPLOYMENT.md'}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=str(MODEL_DIR / "hb_regressor_best.pt"))
    parser.add_argument("--output-dir", default=str(PROJECT_ROOT))
    args = parser.parse_args()

    run_deployment_check(model_path=args.model, output_dir=args.output_dir)
    print("\nPhase J complete.")
