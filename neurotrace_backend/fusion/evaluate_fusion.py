"""
fusion/evaluate_fusion.py
═════════════════════════
Compare all three fusion strategies:
  1. Simple average
  2. Weighted average
  3. Meta-model (trained)

Produces a comparison table and saves plots.

Run:
    python evaluate_fusion.py --model ml_models/fusion_model.pkl
"""

import os
import sys
import numpy as np
import pandas as pd
import joblib
import warnings
warnings.filterwarnings("ignore")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sklearn.metrics import (
    roc_auc_score, accuracy_score, f1_score,
    precision_score, recall_score,
    confusion_matrix, roc_curve,
)
from sklearn.model_selection import train_test_split
from fusion_trainer import (
    FusionEnsemble, FusionPredictor,
    FUSION_FEATURES, generate_pseudo_dataset
)


def evaluate_all_methods(
    model_path:  str = "ml_models/fusion_model.pkl",
    data_path:   str = "data/fusion_training_data.csv",
    test_size:   float = 0.3,
    output_dir:  str = "reports",
):
    """
    Full evaluation of all fusion methods.
    Prints a comparison table and saves an HTML report.
    """
    os.makedirs(output_dir, exist_ok=True)

    # ── Load data ─────────────────────────────────────────────
    if not os.path.exists(data_path):
        print("Generating synthetic data for evaluation...")
        df = generate_pseudo_dataset(output_path=data_path)
    else:
        df = pd.read_csv(data_path)

    X = df[FUSION_FEATURES].fillna(0.5)
    y = df["label"]

    _, X_test, _, y_test = train_test_split(
        X, y, test_size=test_size, stratify=y, random_state=42
    )

    print(f"\nEvaluation set: {len(X_test)} samples  ({y_test.sum()} PD / {(y_test==0).sum()} No-PD)")

    # ── Load fusion model ─────────────────────────────────────
    ensemble = FusionEnsemble()
    if os.path.exists(model_path):
        ensemble = FusionEnsemble.load(model_path)
        print(f"Loaded trained model from: {model_path}")
    else:
        print("No trained model found. Training on synthetic data...")
        _, X_train, _, y_train = train_test_split(X, y, test_size=test_size, stratify=y, random_state=42)
        ensemble.fit(X_train, y_train)

    # ── Compute predictions ────────────────────────────────────
    results = {"Simple Average": [], "Weighted Average": [], "Meta-Model": []}

    for _, row in X_test.iterrows():
        d = row.to_dict()
        results["Simple Average"].append(ensemble.simple_average(d))
        results["Weighted Average"].append(ensemble.weighted_average(d))
        results["Meta-Model"].append(ensemble.meta_predict(d))

    # ── Metrics table ──────────────────────────────────────────
    print("\n" + "="*75)
    print(f"  {'Method':<22}  {'AUC':>7}  {'Acc':>7}  {'F1':>7}  {'Prec':>7}  {'Recall':>7}")
    print("="*75)

    report_rows = []
    for method_name, probs in results.items():
        probs  = np.array(probs)
        preds  = (probs >= 0.5).astype(int)
        auc    = roc_auc_score(y_test, probs)
        acc    = accuracy_score(y_test, preds)
        f1     = f1_score(y_test, preds, zero_division=0)
        prec   = precision_score(y_test, preds, zero_division=0)
        rec    = recall_score(y_test, preds, zero_division=0)

        marker = "  ← BEST" if method_name == "Meta-Model" else ""
        print(f"  {method_name:<22}  {auc:>7.4f}  {acc:>7.4f}  {f1:>7.4f}  {prec:>7.4f}  {rec:>7.4f}{marker}")

        report_rows.append({
            "Method":    method_name,
            "AUC":       round(auc, 4),
            "Accuracy":  round(acc, 4),
            "F1 Score":  round(f1,  4),
            "Precision": round(prec, 4),
            "Recall":    round(rec, 4),
        })

    print("="*75)

    # ── Confusion matrix for meta-model ───────────────────────
    meta_preds = (np.array(results["Meta-Model"]) >= 0.5).astype(int)
    cm         = confusion_matrix(y_test, meta_preds)
    tn, fp, fn, tp = cm.ravel()

    print(f"\n  Meta-Model Confusion Matrix:")
    print(f"              Predicted No-PD  Predicted PD")
    print(f"  Actual No-PD      {tn:>5}            {fp:>5}")
    print(f"  Actual PD         {fn:>5}            {tp:>5}")
    print(f"\n  Sensitivity (Recall): {tp/(tp+fn):.4f}   ← critical for medical use")
    print(f"  Specificity:          {tn/(tn+fp):.4f}")

    # ── Missing modality robustness test ──────────────────────
    print("\n" + "-"*60)
    print("  Robustness Test: Missing Modalities")
    print("-"*60)
    combos = [
        ("All 5 modalities",          ["voice","clinical","mri","spiral","motor"]),
        ("Voice + MRI only",          ["voice","mri"]),
        ("Clinical + Motor only",     ["clinical","motor"]),
        ("Voice only",                ["voice"]),
        ("MRI only",                  ["mri"]),
    ]
    for label, available_mods in combos:
        partial_X = X_test.copy()
        for mod in ["voice","clinical","mri","spiral","motor"]:
            if mod not in available_mods:
                partial_X[f"{mod}_prob"]      = 0.5
                partial_X[f"{mod}_available"] = 0
            else:
                partial_X[f"{mod}_available"] = 1

        probs = np.array([ensemble.meta_predict(row.to_dict()) for _, row in partial_X.iterrows()])
        preds = (probs >= 0.5).astype(int)
        auc   = roc_auc_score(y_test, probs)
        acc   = accuracy_score(y_test, preds)
        print(f"  {label:<30}  AUC={auc:.4f}  Acc={acc:.4f}")

    # ── Save HTML report ───────────────────────────────────────
    report_path = os.path.join(output_dir, "fusion_evaluation.html")
    _save_html_report(pd.DataFrame(report_rows), tn, fp, fn, tp, report_path)
    print(f"\n  Report saved: {report_path}")

    return pd.DataFrame(report_rows)


def _save_html_report(metrics_df, tn, fp, fn, tp, path):
    html = f"""
<!DOCTYPE html>
<html>
<head>
  <title>NeuroTrace Fusion Model — Evaluation Report</title>
  <style>
    body {{ font-family: 'Segoe UI', sans-serif; background:#0a0e1a; color:#e0e8ff; padding:40px; }}
    h1   {{ color:#00d4ff; font-size:24px; border-bottom:2px solid #00d4ff; padding-bottom:10px; }}
    h2   {{ color:#7b5cff; font-size:18px; margin-top:32px; }}
    table {{ border-collapse:collapse; width:100%; margin:16px 0; }}
    th {{ background:#131a30; color:#8892b0; font-size:12px; letter-spacing:1px; text-transform:uppercase; padding:10px 14px; }}
    td {{ padding:10px 14px; border-bottom:1px solid #1a2240; font-size:14px; }}
    tr.best {{ background:rgba(0,212,255,0.08); }}
    .good {{ color:#00e5a0; }}
    .badge {{ padding:3px 10px; border-radius:99px; font-size:11px; }}
    .best-badge {{ background:rgba(0,212,255,0.15); color:#00d4ff; }}
  </style>
</head>
<body>
  <h1>🧠 NeuroTrace — Fusion Model Evaluation Report</h1>
  <p style="color:#8892b0">Parkinson's Disease Multi-Modal Fusion — Evaluation on hold-out test set</p>

  <h2>Method Comparison</h2>
  <table>
    <tr><th>Method</th><th>AUC</th><th>Accuracy</th><th>F1 Score</th><th>Precision</th><th>Recall</th><th></th></tr>
    {"".join(
        f'<tr class="{"best" if row["Method"]=="Meta-Model" else ""}">'
        f'<td>{row["Method"]}</td>'
        f'<td class="good">{row["AUC"]}</td>'
        f'<td>{row["Accuracy"]}</td>'
        f'<td>{row["F1 Score"]}</td>'
        f'<td>{row["Precision"]}</td>'
        f'<td>{row["Recall"]}</td>'
        f'<td>{"<span class=\'badge best-badge\'>Best</span>" if row["Method"]=="Meta-Model" else ""}</td>'
        f'</tr>'
        for _, row in metrics_df.iterrows()
    )}
  </table>

  <h2>Meta-Model Confusion Matrix</h2>
  <table style="width:auto">
    <tr><th></th><th>Predicted No-PD</th><th>Predicted PD</th></tr>
    <tr><td><b>Actual No-PD</b></td><td class="good">{tn} (TN)</td><td style="color:#ff4e6a">{fp} (FP)</td></tr>
    <tr><td><b>Actual PD</b></td><td style="color:#ff4e6a">{fn} (FN)</td><td class="good">{tp} (TP)</td></tr>
  </table>
  <p style="color:#8892b0;font-size:13px">
    Sensitivity: <span class="good">{tp/(tp+fn):.4f}</span> &nbsp;|&nbsp;
    Specificity: <span class="good">{tn/(tn+fp):.4f}</span>
  </p>
</body>
</html>"""
    with open(path, "w") as f:
        f.write(html)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="ml_models/fusion_model.pkl")
    parser.add_argument("--data",  default="data/fusion_training_data.csv")
    args = parser.parse_args()
    evaluate_all_methods(model_path=args.model, data_path=args.data)