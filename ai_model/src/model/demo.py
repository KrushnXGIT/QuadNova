"""Demonstrate CV-to-model integration without claiming an Hb prediction.

This intentionally uses the existing synthetic CV fixtures. The model is
untrained, so its numeric output is only a forward-pass smoke value and must
never be interpreted as haemoglobin.
"""

import argparse
import json
from pathlib import Path

import torch

from src.data.matching import scan_raw_data_dir
from src.vision.pipeline import process_subject
from .model import HbRegressor


def run_demo(raw_dir="tests/synthetic_fixtures/raw", subject_id=None):
    records, _ = scan_raw_data_dir(raw_dir)
    candidates = [
        (sid, record) for sid, record in records.items()
        if record.raw_photo and record.mask_forniceal_palpebral
    ]
    if not candidates:
        raise RuntimeError(f"No complete raw+mask subject found in {raw_dir}")
    sid, record = next((item for item in candidates if item[0] == subject_id), candidates[0]) if subject_id else candidates[0]
    result = process_subject(
        sid,
        str(Path(raw_dir) / record.raw_photo),
        str(Path(raw_dir) / record.mask_forniceal_palpebral),
    )
    if not result.accepted:
        return {"subject_id": sid, "quality_status": "rejected", "quality_report": result.quality_report}

    model = HbRegressor(pretrained=False).eval()
    image = torch.from_numpy(result.roi_tensor.transpose(2, 0, 1)).unsqueeze(0).float()
    with torch.no_grad():
        output = float(model(image).item())
    return {
        "subject_id": sid,
        "quality_status": "accepted",
        "roi_shape": list(result.roi_tensor.shape),
        "model": "MobileNetV3-small regression head",
        "device": "cpu",
        "untrained_forward_output": output,
        "warning": "This is not an Hb estimate. A verified Hb-labeled checkpoint is required.",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", default="tests/synthetic_fixtures/raw")
    parser.add_argument("--subject-id")
    args = parser.parse_args()
    print(json.dumps(run_demo(args.raw_dir, args.subject_id), indent=2))


if __name__ == "__main__":
    main()
