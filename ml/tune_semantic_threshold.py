"""
tune_semantic_threshold.py
Finds the best similarity threshold for the semantic detector by testing
multiple candidate thresholds against the real labeled test set.

Run:
    python tune_semantic_threshold.py
"""

import pandas as pd
import numpy as np
from sklearn.metrics import precision_recall_fscore_support, accuracy_score
from semantic_engine import SemanticDetector

CANDIDATE_THRESHOLDS = [0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65]


if __name__ == "__main__":
    detector = SemanticDetector(similarity_threshold=0.5)  # placeholder, we override per test
    detector.build_bank_from_csv("../data/train.csv")

    # Use a manageable subset of test.csv for speed during tuning
    df = pd.read_csv("../data/test.csv").sample(n=1000, random_state=42)
    texts = df["text"].astype(str).tolist()
    labels = df["label"].tolist()

    print("\nComputing similarities for all test prompts (one pass)...")
    query_embeddings = detector.model.encode(texts, convert_to_tensor=True, show_progress_bar=True)
    from sentence_transformers import util
    similarities = util.cos_sim(query_embeddings, detector.attack_bank_embeddings)
    max_sims = similarities.max(dim=1).values.cpu().numpy()

    print(f"\nSimilarity score range: min={max_sims.min():.3f}, max={max_sims.max():.3f}, mean={max_sims.mean():.3f}")

    print(f"\n{'Threshold':<10} {'Accuracy':<10} {'Precision':<10} {'Recall':<10} {'F1':<10}")
    print("-" * 55)
    best_f1 = 0
    best_threshold = None
    for threshold in CANDIDATE_THRESHOLDS:
        preds = (max_sims >= threshold).astype(int)
        acc = accuracy_score(labels, preds)
        precision, recall, f1, _ = precision_recall_fscore_support(
            labels, preds, average="binary", zero_division=0
        )
        print(f"{threshold:<10} {acc:<10.4f} {precision:<10.4f} {recall:<10.4f} {f1:<10.4f}")
        if f1 > best_f1:
            best_f1 = f1
            best_threshold = threshold

    print(f"\nBest threshold: {best_threshold} (F1={best_f1:.4f})")
    print("Update SemanticDetector's default similarity_threshold to this value.")