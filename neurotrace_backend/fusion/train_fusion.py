"""
fusion/train_fusion.py
══════════════════════
One-command fusion model trainer.

Quick Start:
    # Step 1: Train on synthetic data (immediate, no datasets needed)
    python train_fusion.py

    # Step 2: Train on your real voice dataset (once you have it)
    python train_fusion.py --voice-data path/to/parkinsons_voice.csv

    # Step 3: Train with XGBoost (best accuracy)
    python train_fusion.py --type xgboost

    # Step 4: Evaluate
    python evaluate_fusion.py

The trained model is saved to ml_models/fusion_model.pkl
and is automatically picked up by the Flask app on next restart.
"""

import os
import sys
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fusion_trainer import generate_pseudo_dataset, train_fusion_model
from collect_real_training_data import collect_all


def main():
    parser = argparse.ArgumentParser(
        description="Train NeuroTrace Fusion Model",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python train_fusion.py                              # synthetic data, logistic regression
  python train_fusion.py --type xgboost              # XGBoost meta-model (best)
  python train_fusion.py --voice-data park.csv       # use real voice dataset
  python train_fusion.py --n-samples 1000            # more synthetic samples
        """
    )
    parser.add_argument("--voice-data",    default=None,                        help="Path to voice CSV dataset")
    parser.add_argument("--clinical-data", default=None,                        help="Path to clinical CSV dataset")
    parser.add_argument("--data",          default="data/fusion_training_data.csv", help="Fusion training data CSV")
    parser.add_argument("--model",         default="ml_models/fusion_model.pkl",   help="Output model path")
    parser.add_argument("--type",          default="logistic",
                        choices=["logistic","random_forest","xgboost"],          help="Meta-model type")
    parser.add_argument("--n-samples",     type=int, default=500,               help="Synthetic sample count")
    parser.add_argument("--evaluate",      action="store_true",                 help="Run evaluation after training")
    args = parser.parse_args()

    print("\n" + "="*60)
    print("  NeuroTrace — Fusion Model Trainer")
    print("="*60)

    # ── Step 1: Collect or generate training data ─────────────
    if args.voice_data or args.clinical_data:
        print("\nCollecting real data from base models...")
        df = collect_all(
            voice_csv    = args.voice_data,
            clinical_csv = args.clinical_data,
            output_path  = args.data,
        )
        if df is None:
            print("No data collected. Falling back to synthetic data.")
            generate_pseudo_dataset(output_path=args.data, n_synthetic=args.n_samples)
    elif not os.path.exists(args.data):
        print(f"\nNo data at {args.data}. Generating {args.n_samples} synthetic samples...")
        generate_pseudo_dataset(output_path=args.data, n_synthetic=args.n_samples)
    else:
        print(f"\nUsing existing data: {args.data}")

    # ── Step 2: Train ─────────────────────────────────────────
    fusion = train_fusion_model(
        data_path       = args.data,
        model_save_path = args.model,
        meta_model_type = args.type,
    )

    # ── Step 3: Evaluate (optional) ───────────────────────────
    if args.evaluate:
        print("\nRunning evaluation...")
        from evaluate_fusion import evaluate_all_methods
        evaluate_all_methods(model_path=args.model, data_path=args.data)

    print("\n" + "="*60)
    print("  DONE!")
    print(f"\n  Model: {args.model}")
    print(f"  CV AUC: {fusion.training_metrics.get('cv_auc_mean','?'):.4f}")
    print()
    print("  Next steps:")
    print("  1. Copy fusion_model.pkl → your ml_models/ folder")
    print("  2. Restart Flask: python run.py")
    print("  3. The meta-model is now active for all /api/fusion/* calls")
    print("="*60)


if __name__ == "__main__":
    main()