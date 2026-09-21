"""
tune_fusion.py
Finds the optimal weighted-fusion combination (weights + threshold) by
grid-searching against the validation set. Also trains a logistic regression
meta-classifier on the same 3 detector scores as a comparison point.

This gives you two real, tuned fusion strategies to compare in your ablation study.

Run:
    python tune_fusion.py
"""

import itertools
import numpy as np
import pandas as pd
import torch
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import precision_recall_fscore_support, accuracy_score
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from rules_engine import check_rules
from semantic_engine import SemanticDetector

MODEL_DIR = "./final_model"
SAMPLE_SIZE = 1500  # subset of val.csv for speed during tuning


def get_raw_scores(df):
    """Runs all 3 detectors on every row, returns a DataFrame of raw scores + true labels."""
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Loading classifier on {device}...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR)
    model = AutoModelForSequenceClassification.from_pretrained(MODEL_DIR).to(device)
    model.eval()

    print("Loading semantic detector...")
    semantic = SemanticDetector(similarity_threshold=0.45)
    semantic.build_bank_from_csv("../data/train.csv")

    print(f"Scoring {len(df)} validation rows with all 3 detectors...")
    classifier_scores, semantic_scores, rules_scores, labels = [], [], [], []

    texts = df["text"].astype(str).tolist()

    # Batch classifier scoring for speed
    batch_size = 32
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i+batch_size]
        inputs = tokenizer(batch, truncation=True, padding=True, max_length=128, return_tensors="pt").to(device)
        with torch.no_grad():
            probs = torch.softmax(model(**inputs).logits, dim=-1)
        classifier_scores.extend(probs[:, 1].cpu().numpy().tolist())

    # Batch semantic scoring
    semantic_results = semantic.check_batch(texts)
    semantic_scores = [r["max_similarity"] for r in semantic_results]

    # Rules (fast enough row by row)
    for text in texts:
        r = check_rules(text)
        rules_scores.append(r["max_weight"])

    return pd.DataFrame({
        "classifier": classifier_scores,
        "semantic": semantic_scores,
        "rules": rules_scores,
        "label": df["label"].tolist(),
    })


def grid_search_weights(scores_df):
    """Tries combinations of weights + threshold, returns the best by F1."""
    weight_options = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6]
    threshold_options = [0.35, 0.4, 0.45, 0.5, 0.55, 0.6]

    best_f1 = 0
    best_config = None

    for w_clf, w_sem, w_rules in itertools.product(weight_options, repeat=3):
        total = w_clf + w_sem + w_rules
        if total == 0:
            continue
        w_clf, w_sem, w_rules = w_clf / total, w_sem / total, w_rules / total  # normalize to sum=1

        combined = (
            w_clf * scores_df["classifier"] +
            w_sem * scores_df["semantic"] +
            w_rules * scores_df["rules"]
        )

        for threshold in threshold_options:
            preds = (combined >= threshold).astype(int)
            precision, recall, f1, _ = precision_recall_fscore_support(
                scores_df["label"], preds, average="binary", zero_division=0
            )
            if f1 > best_f1:
                best_f1 = f1
                best_config = {
                    "w_classifier": round(w_clf, 3),
                    "w_semantic": round(w_sem, 3),
                    "w_rules": round(w_rules, 3),
                    "threshold": threshold,
                    "f1": round(f1, 4),
                    "precision": round(precision, 4),
                    "recall": round(recall, 4),
                }

    return best_config


def train_meta_classifier(scores_df):
    """Trains a logistic regression on the 3 raw scores as features."""
    X = scores_df[["classifier", "semantic", "rules"]].values
    y = scores_df["label"].values

    clf = LogisticRegression()
    clf.fit(X, y)
    preds = clf.predict(X)

    precision, recall, f1, _ = precision_recall_fscore_support(y, preds, average="binary", zero_division=0)
    acc = accuracy_score(y, preds)

    print(f"\nMeta-classifier learned coefficients:")
    print(f"  classifier weight: {clf.coef_[0][0]:.4f}")
    print(f"  semantic weight:   {clf.coef_[0][1]:.4f}")
    print(f"  rules weight:      {clf.coef_[0][2]:.4f}")
    print(f"  intercept:         {clf.intercept_[0]:.4f}")

    return clf, {"accuracy": acc, "precision": precision, "recall": recall, "f1": f1}


if __name__ == "__main__":
    print("Loading validation data...")
    val_df = pd.read_csv("../data/val.csv")
    if len(val_df) > SAMPLE_SIZE:
        val_df = val_df.sample(n=SAMPLE_SIZE, random_state=42)

    scores_df = get_raw_scores(val_df)
    scores_df.to_csv("../data/val_detector_scores.csv", index=False)
    print(f"\nSaved raw scores to ../data/val_detector_scores.csv")

    print("\n" + "="*50)
    print("GRID SEARCH: Weighted Fusion")
    print("="*50)
    best_weighted = grid_search_weights(scores_df)
    print(f"\nBest weighted-fusion config:")
    for k, v in best_weighted.items():
        print(f"  {k}: {v}")

    print("\n" + "="*50)
    print("META-CLASSIFIER: Logistic Regression")
    print("="*50)
    meta_clf, meta_metrics = train_meta_classifier(scores_df)
    print(f"\nMeta-classifier performance (on val set):")
    for k, v in meta_metrics.items():
        print(f"  {k}: {v:.4f}")

    print("\n" + "="*50)
    print("COMPARISON")
    print("="*50)
    print(f"Tuned weighted fusion : F1={best_weighted['f1']:.4f} | P={best_weighted['precision']:.4f} | R={best_weighted['recall']:.4f}")
    print(f"Meta-classifier fusion: F1={meta_metrics['f1']:.4f} | P={meta_metrics['precision']:.4f} | R={meta_metrics['recall']:.4f}")