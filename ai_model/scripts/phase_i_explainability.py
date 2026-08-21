"""
phase_i_explainability.py
==========================
PHASE I: Grad-CAM Explainability

Generates Grad-CAM visualizations for accepted subjects to verify whether
the model focuses on the conjunctiva ROI rather than irrelevant regions.

DISCLAIMER: Explainability does NOT prove medical validity.
Grad-CAM shows which regions activate the model, not which regions
are clinically meaningful. A model that focuses on the conjunctiva
may still be poorly calibrated.

Produces:
  results/explainability/gradcam_<subject_id>.png
  results/explainability/README.md
"""

import sys
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.model.config import MODEL_DIR, RESULTS_DIR, SPLIT_PATH, QUALITY_OVERRIDES
from src.model.model import HbRegressor
from src.data.matching import scan_raw_data_dir
from src.data.splitting import load_split
from src.vision.pipeline import process_subject

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import cv2
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False


class GradCAM:
    """Minimal Grad-CAM implementation for HbRegressor."""

    def __init__(self, model: HbRegressor):
        self.model = model
        self.gradients = None
        self.activations = None
        self._hook_handle_fw = None
        self._hook_handle_bw = None

    def _register_hooks(self):
        # Hook on the last conv layer of the feature extractor
        # MobileNetV3-small: features[-1] is the last layer before pooling
        target_layer = self.model.features[-1]

        def forward_hook(module, input, output):
            self.activations = output.detach()

        def backward_hook(module, grad_input, grad_output):
            self.gradients = grad_output[0].detach()

        self._hook_handle_fw = target_layer.register_forward_hook(forward_hook)
        self._hook_handle_bw = target_layer.register_full_backward_hook(backward_hook)

    def _remove_hooks(self):
        if self._hook_handle_fw:
            self._hook_handle_fw.remove()
        if self._hook_handle_bw:
            self._hook_handle_bw.remove()

    def compute(self, image_tensor: torch.Tensor) -> np.ndarray:
        """
        Compute Grad-CAM for a single image.

        Args:
            image_tensor: (1, 3, H, W) float tensor.

        Returns:
            (H, W) float32 array — Grad-CAM heatmap, values in [0, 1].
        """
        self._register_hooks()
        try:
            image_tensor = image_tensor.clone().requires_grad_(True)
            self.model.eval()

            # Forward pass
            output = self.model(image_tensor)
            output.backward()

            # Grad-CAM weights: global average pool of gradients
            weights = self.gradients.mean(dim=(2, 3), keepdim=True)
            cam = (weights * self.activations).sum(dim=1, keepdim=True)
            cam = F.relu(cam)

            # Resize to input size
            cam = F.interpolate(
                cam,
                size=(image_tensor.shape[2], image_tensor.shape[3]),
                mode="bilinear",
                align_corners=False,
            )
            cam = cam.squeeze().numpy()
            if cam.max() > 0:
                cam = cam / cam.max()

            return cam.astype(np.float32)
        finally:
            self._remove_hooks()


def run_explainability(
    raw_dir: str = "data/raw/verified_flat",
    metadata_dir: str = "data/metadata",
    split_path: str = None,
    model_path: str = None,
    output_dir: str = None,
    max_subjects: int = 6,
):
    split_path = split_path or str(SPLIT_PATH)
    model_path = model_path or str(MODEL_DIR / "hb_regressor_best.pt")
    output_dir = Path(output_dir or (Path(RESULTS_DIR) / "explainability"))
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=== PHASE I: Explainability (Grad-CAM) ===")

    if not MATPLOTLIB_AVAILABLE:
        print("  SKIPPED: matplotlib not available")
        _write_readme(output_dir, skipped=True, reason="matplotlib not available")
        return

    split_data = load_split(split_path)["split"]
    records, _ = scan_raw_data_dir(raw_dir)

    checkpoint = torch.load(model_path, map_location="cpu", weights_only=False)
    config = checkpoint.get("config", {})
    target_mean = config.get("target_mean", 0.0)
    target_std = config.get("target_std", 1.0)

    model = HbRegressor(
        pretrained=config.get("pretrained", False),
        freeze_backbone=config.get("freeze_backbone", False),
    )
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()

    gradcam = GradCAM(model)
    generated = []

    # Try subjects from test set first, then val
    candidates = split_data.get("test", []) + split_data.get("val", [])

    for sid in candidates[:max_subjects * 2]:
        if len(generated) >= max_subjects:
            break

        record = records.get(sid)
        if record is None or not record.raw_photo or not record.mask_forniceal_palpebral:
            continue

        raw_path = str(Path(raw_dir) / record.raw_photo)
        mask_path = str(Path(raw_dir) / record.mask_forniceal_palpebral)

        result = process_subject(sid, raw_path, mask_path, quality_overrides=QUALITY_OVERRIDES)
        if not result.accepted or result.roi_tensor is None:
            continue

        roi_tensor = result.roi_tensor  # (H, W, 3) float32
        image_tensor = torch.from_numpy(roi_tensor.transpose(2, 0, 1)).unsqueeze(0).float()

        try:
            cam = gradcam.compute(image_tensor)
        except Exception as e:
            print(f"  Grad-CAM failed for {sid}: {e}")
            continue

        # Prediction
        with torch.no_grad():
            pred_raw = float(model(image_tensor).item())
        pred = pred_raw * target_std + target_mean

        # Visualization
        fig, axes = plt.subplots(1, 3, figsize=(12, 4))

        # Original ROI
        axes[0].imshow(roi_tensor)
        axes[0].set_title(f"ROI: {sid}\nPred Hb = {pred:.1f} g/dL")
        axes[0].axis("off")

        # Grad-CAM heatmap
        axes[1].imshow(cam, cmap="jet")
        axes[1].set_title("Grad-CAM Heatmap")
        axes[1].axis("off")

        # Overlay
        cam_colored = plt.cm.jet(cam)[:, :, :3]
        overlay = 0.5 * roi_tensor + 0.5 * cam_colored.astype(np.float32)
        overlay = np.clip(overlay, 0, 1)
        axes[2].imshow(overlay)
        axes[2].set_title("Overlay")
        axes[2].axis("off")

        fig.suptitle(
            "Grad-CAM: red = high model attention | "
            "DISCLAIMER: Does not prove medical validity",
            fontsize=9, color="gray"
        )
        plt.tight_layout()

        save_path = output_dir / f"gradcam_{sid}.png"
        plt.savefig(save_path, dpi=100, bbox_inches="tight")
        plt.close(fig)
        print(f"  Saved: {save_path}")
        generated.append(str(save_path))

    _write_readme(output_dir, skipped=False, generated=generated)
    print(f"\nGenerated {len(generated)} Grad-CAM visualizations.")
    return generated


def _write_readme(output_dir: Path, skipped=False, reason="", generated=None):
    lines = [
        "# Explainability — Grad-CAM Visualizations",
        "",
        "## Disclaimer",
        "",
        "**Grad-CAM does NOT prove medical validity.**",
        "",
        "These visualizations show which image regions most strongly activate the model's "
        "prediction. They can help verify that the model focuses on the conjunctiva tissue "
        "rather than irrelevant regions (e.g., eyelashes, background). However:",
        "",
        "- A model that focuses on the conjunctiva may still be poorly calibrated.",
        "- Grad-CAM is a post-hoc saliency method, not a causal explanation.",
        "- Misaligned attention does not necessarily mean the prediction is wrong.",
        "- Correct attention does not necessarily mean the prediction is right.",
        "",
    ]

    if skipped:
        lines += [
            f"## Status: SKIPPED",
            f"Reason: {reason}",
        ]
    else:
        lines += [
            "## Generated Visualizations",
            "",
            "Each image shows: original ROI | Grad-CAM heatmap | Overlay",
            "",
            "Red/yellow = high model attention. Blue = low model attention.",
            "",
        ]
        if generated:
            for p in generated:
                lines.append(f"- `{Path(p).name}`")
        else:
            lines.append("No visualizations generated (no accepted subjects found).")

    (output_dir / "README.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", default="data/raw/verified_flat")
    parser.add_argument("--metadata-dir", default="data/metadata")
    parser.add_argument("--split", default=str(SPLIT_PATH))
    parser.add_argument("--model", default=str(MODEL_DIR / "hb_regressor_best.pt"))
    parser.add_argument("--output-dir", default=str(Path(RESULTS_DIR) / "explainability"))
    parser.add_argument("--max-subjects", type=int, default=6)
    args = parser.parse_args()

    run_explainability(
        raw_dir=args.raw_dir,
        metadata_dir=args.metadata_dir,
        split_path=args.split,
        model_path=args.model,
        output_dir=args.output_dir,
        max_subjects=args.max_subjects,
    )
    print("\nPhase I complete.")
