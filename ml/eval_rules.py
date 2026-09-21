"""
eval_rules.py
Evaluates the rule-based engine alone against the real test set.
This gives us the "rules-only" data point for your ablation study
(rules-only vs. classifier-only vs. combined).

Run:
    python eval_rules.py
"""

import pandas as pd
from sklearn.metrics import accuracy_score, precision_recall_fscore_support, confusion_matrix
from rules_engine import check_rules


def evaluate_rules(filepath, name):
    print(f"\n{'='*50}")
    print(f"Evaluating rules engine on: {name} ({filepath})")
    print(f"{'='*50}")

    df = pd.read_csv(filepath)
    preds = []
    for text in df["text"]:
        result = check_rules(str(text))
        # A rule match of ANY weight counts as a "malicious" prediction here.
        # (We can raise this threshold later during fusion tuning.)
        preds.append(1 if result["matched"] else 0)

    labels = df["label"].tolist()

    acc = accuracy_score(labels, preds)
    precision, recall, f1, _ = precision_recall_fscore_support(labels, preds, average="binary", zero_division=0)
    cm = confusion_matrix(labels, preds)

    print(f"Rows evaluated: {len(df)}")
    print(f"Accuracy:  {acc:.4f}")
    print(f"Precision: {precision:.4f}")
    print(f"Recall:    {recall:.4f}")
    print(f"F1:        {f1:.4f}")
    print(f"Confusion matrix (rows=actual, cols=predicted):")
    print(f"                 Pred Benign   Pred Malicious")
    print(f"Actual Benign    {cm[0][0]:<13} {cm[0][1]}")
    print(f"Actual Malicious {cm[1][0]:<13} {cm[1][1]}")

    return {"name": name, "accuracy": acc, "precision": precision, "recall": recall, "f1": f1}


if __name__ == "__main__":
    test_results = evaluate_rules("../data/test.csv", "Held-out Test Set")
    zero_day_results = evaluate_rules("../data/zero_day_test.csv", "Zero-Day Holdout")

    print(f"\n{'='*50}")
    print("SUMMARY - Rules Engine Alone")
    print(f"{'='*50}")
    for r in [test_results, zero_day_results]:
        print(f"{r['name']}: Acc={r['accuracy']:.4f} | Prec={r['precision']:.4f} | Recall={r['recall']:.4f} | F1={r['f1']:.4f}")