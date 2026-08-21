"""
run_all_phases.py
=================
Master orchestrator for the complete AI pipeline completion.
Runs all phases sequentially in the correct order.

Usage:
    python scripts/run_all_phases.py --raw-dir data/raw/verified_flat
"""

import argparse
import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.model.config import MODEL_DIR, RESULTS_DIR, SPLIT_PATH


def run_phase(name, fn, *args, **kwargs):
    print(f"\n{'='*60}")
    print(f"STARTING: {name}")
    print(f"{'='*60}")
    t0 = time.time()
    try:
        result = fn(*args, **kwargs)
        elapsed = time.time() - t0
        print(f"COMPLETED: {name} in {elapsed:.1f}s")
        return result
    except Exception as e:
        elapsed = time.time() - t0
        print(f"ERROR in {name} after {elapsed:.1f}s: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", default="data/raw/verified_flat")
    parser.add_argument("--metadata-dir", default="data/metadata")
    parser.add_argument("--split", default=str(SPLIT_PATH))
    parser.add_argument("--model", default=str(MODEL_DIR / "hb_regressor_best.pt"))
    parser.add_argument("--results-dir", default=str(RESULTS_DIR))
    parser.add_argument("--model-dir", default=str(MODEL_DIR))
    parser.add_argument("--cache-dir", default="data/processed/model_cache")
    parser.add_argument("--skip-norm-experiments", action="store_true",
                        help="Skip normalization comparison (slow — trains 4 models)")
    parser.add_argument("--skip-explainability", action="store_true",
                        help="Skip Grad-CAM explainability (requires matplotlib)")
    args = parser.parse_args()

    results_dir = Path(args.results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ #
    # PHASE A: Domain Analysis
    # ------------------------------------------------------------------ #
    from scripts.phase_a_domain_analysis import run_domain_analysis, write_domain_analysis_md, write_hb_range_analysis_md

    phase_a_result = run_phase(
        "PHASE A: Domain Analysis",
        run_domain_analysis,
        raw_dir=args.raw_dir,
        metadata_dir=args.metadata_dir,
        split_path=args.split,
        model_path=args.model,
        cache_dir=args.cache_dir,
        output_dir=args.results_dir,
    )
    if phase_a_result:
        metrics, frame = phase_a_result
        write_domain_analysis_md(metrics, results_dir)
        write_hb_range_analysis_md(metrics, frame, results_dir)

    # ------------------------------------------------------------------ #
    # PHASE B: ROI Quality Audit
    # ------------------------------------------------------------------ #
    from scripts.phase_b_roi_quality import run_roi_quality_audit, write_roi_quality_md

    phase_b_result = run_phase(
        "PHASE B: ROI Quality Audit",
        run_roi_quality_audit,
        raw_dir=args.raw_dir,
        metadata_dir=args.metadata_dir,
        split_path=args.split,
        model_path=args.model,
        output_dir=args.results_dir,
    )
    if phase_b_result is not None:
        write_roi_quality_md(phase_b_result, results_dir)

    # ------------------------------------------------------------------ #
    # PHASE C: Normalization Experiments
    # ------------------------------------------------------------------ #
    best_norm = "clahe"  # default
    if not args.skip_norm_experiments:
        from scripts.phase_c_normalization import run_normalization_experiments, write_normalization_analysis_md

        phase_c_norm = run_phase(
            "PHASE C: Normalization Comparison",
            run_normalization_experiments,
            raw_dir=args.raw_dir,
            metadata_dir=args.metadata_dir,
            split_path=args.split,
            output_dir=args.results_dir,
            model_dir=args.model_dir,
        )
        if phase_c_norm:
            selected = write_normalization_analysis_md(phase_c_norm, results_dir)
            if selected:
                best_norm = selected
    else:
        print("\nSkipping normalization experiments (--skip-norm-experiments)")
        # Write placeholder
        placeholder = {
            "note": "Skipped by user. Using default clahe.",
            "results": [{"norm_method": "clahe", "val_MAE": None}],
        }
        (results_dir / "normalization_comparison.json").write_text(
            json.dumps(placeholder, indent=2), encoding="utf-8"
        )

    # ------------------------------------------------------------------ #
    # PHASE C: Lighting Robustness
    # ------------------------------------------------------------------ #
    from scripts.phase_c_lighting_robustness import (
        run_lighting_robustness, write_lighting_robustness_md, write_device_robustness_md
    )

    phase_c_light = run_phase(
        "PHASE C: Lighting Robustness",
        run_lighting_robustness,
        raw_dir=args.raw_dir,
        metadata_dir=args.metadata_dir,
        split_path=args.split,
        model_path=args.model,
        norm_method=best_norm,
        output_dir=args.results_dir,
    )
    if phase_c_light:
        write_lighting_robustness_md(phase_c_light, results_dir)
    write_device_robustness_md(results_dir)

    # ------------------------------------------------------------------ #
    # PHASE D: Uncertainty + Confidence Calibration
    # ------------------------------------------------------------------ #
    from scripts.phase_d_uncertainty import (
        run_uncertainty_analysis, write_uncertainty_analysis_md, write_confidence_calibration_md
    )

    phase_d_result = run_phase(
        "PHASE D: Uncertainty Analysis",
        run_uncertainty_analysis,
        raw_dir=args.raw_dir,
        metadata_dir=args.metadata_dir,
        split_path=args.split,
        model_path=args.model,
        output_dir=args.results_dir,
        cache_dir=args.cache_dir,
    )
    if phase_d_result:
        unc_frame, unc_summary, calibrator = phase_d_result
        write_uncertainty_analysis_md(unc_frame, unc_summary, results_dir)
        write_confidence_calibration_md(unc_summary, results_dir)

    # ------------------------------------------------------------------ #
    # PHASE H: Final Model Selection + Test Evaluation
    # ------------------------------------------------------------------ #
    from scripts.phase_h_final_evaluation import run_final_evaluation, write_final_model_report

    phase_h_result = run_phase(
        "PHASE H: Final Test Evaluation",
        run_final_evaluation,
        raw_dir=args.raw_dir,
        metadata_dir=args.metadata_dir,
        split_path=args.split,
        results_dir=args.results_dir,
        model_dir=args.model_dir,
        cache_dir=args.cache_dir,
    )
    if phase_h_result:
        final_data, test_frame = phase_h_result
        write_final_model_report(final_data, results_dir)

    # ------------------------------------------------------------------ #
    # PHASE I: Explainability
    # ------------------------------------------------------------------ #
    if not args.skip_explainability:
        from scripts.phase_i_explainability import run_explainability
        run_phase(
            "PHASE I: Explainability (Grad-CAM)",
            run_explainability,
            raw_dir=args.raw_dir,
            metadata_dir=args.metadata_dir,
            split_path=args.split,
            model_path=args.model,
            output_dir=str(results_dir / "explainability"),
        )

    # ------------------------------------------------------------------ #
    # PHASE J: Deployment Readiness
    # ------------------------------------------------------------------ #
    from scripts.phase_j_deployment import run_deployment_check
    run_phase(
        "PHASE J: Deployment Readiness",
        run_deployment_check,
        model_path=args.model,
        output_dir=PROJECT_ROOT,
    )

    # ------------------------------------------------------------------ #
    # PHASE F: Robustness Summary
    # ------------------------------------------------------------------ #
    from scripts.phase_f_robustness_summary import write_robustness_summary
    write_robustness_summary(results_dir, phase_h_result[0] if phase_h_result else None)

    print(f"\n{'='*60}")
    print("ALL PHASES COMPLETE")
    print(f"Results: {results_dir}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
