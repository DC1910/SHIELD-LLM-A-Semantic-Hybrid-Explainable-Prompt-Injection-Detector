"""
error_analysis.py
Compares classifier-alone predictions vs. fusion predictions on the same data
to find where they DISAGREE - this is the real evidence for whether fusion
adds value beyond the classifier alone, not just aggregate F1 comparison.

Run:
    python error_analysis.py
"""

import pandas as pd
import numpy as np
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from rules_engine import check_rules
from semantic_engine import SemanticDetector

MODEL_DIR = "./final_model"

# Tuned fusion config (from tune_fusion.py results)
W_CLF, W_SEM, W_RULES = 0.25, 0.5, 0.25
FUSION_THRESHOLD = 0.35
CLASSIFIER_THRESHOLD = 0.5  # standard default for classifier-alone


def run_analysis(df, name, tokenizer, model, semantic, device):
    print(f"\n{'#'*60}")
    print(f"# {name}")
    print(f"{'#'*60}")

    texts = df["text"].astype(str).tolist()
    labels = df["label"].tolist()

    print(f"Scoring {len(df)} rows...")
    classifier_scores = []
    batch_size = 32
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i+batch_size]
        inputs = tokenizer(batch, truncation=True, padding=True, max_length=128, return_tensors="pt").to(device)
        with torch.no_grad():
            probs = torch.softmax(model(**inputs).logits, dim=-1)
        classifier_scores.extend(probs[:, 1].cpu().numpy().tolist())

    semantic_results = semantic.check_batch(texts)
    semantic_scores = [r["max_similarity"] for r in semantic_results]

    rules_scores = [check_rules(t)["max_weight"] for t in texts]

    results_df = pd.DataFrame({
        "text": texts,
        "label": labels,
        "classifier_score": classifier_scores,
        "semantic_score": semantic_scores,
        "rules_score": rules_scores,
    })

    results_df["classifier_pred"] = (results_df["classifier_score"] >= CLASSIFIER_THRESHOLD).astype(int)

    # Confidence-gated fusion (matches updated fusion_engine.py logic)
    # Vectorized with numpy instead of .apply() - .apply() loops row-by-row in pure
    # Python and is very slow on 90k+ rows; np.where does this in compiled C, much faster.
    CONFIDENT_HIGH, CONFIDENT_LOW = 0.50, 0.15

    clf = results_df["classifier_score"].values
    sem = results_df["semantic_score"].values
    rul = results_df["rules_score"].values

    is_confident = (clf >= CONFIDENT_HIGH) | (clf <= CONFIDENT_LOW)

    blended = W_CLF * clf + W_SEM * sem + W_RULES * rul
    fusion_score = np.where(is_confident, clf, blended)

    # Strong rule match boost (vectorized)
    strong_rule = rul >= 0.8
    fusion_score = np.where(strong_rule, np.maximum(fusion_score, 0.75), fusion_score)

    results_df["fusion_score"] = fusion_score
    results_df["fusion_pred"] = (results_df["fusion_score"] >= FUSION_THRESHOLD).astype(int)

    results_df["classifier_correct"] = results_df["classifier_pred"] == results_df["label"]
    results_df["fusion_correct"] = results_df["fusion_pred"] == results_df["label"]

    both_correct = ((results_df["classifier_correct"]) & (results_df["fusion_correct"])).sum()
    both_wrong = ((~results_df["classifier_correct"]) & (~results_df["fusion_correct"])).sum()
    fusion_fixed = ((~results_df["classifier_correct"]) & (results_df["fusion_correct"])).sum()
    fusion_broke = ((results_df["classifier_correct"]) & (~results_df["fusion_correct"])).sum()

    print(f"\nTotal examples: {len(results_df)}")
    print(f"Both correct:                            {both_correct}")
    print(f"Both wrong:                               {both_wrong}")
    print(f"Fusion FIXED (clf wrong, fusion right):   {fusion_fixed}")
    print(f"Fusion BROKE (clf right, fusion wrong):   {fusion_broke}")
    net_gain = fusion_fixed - fusion_broke
    print(f"\nNet gain from fusion: {net_gain} examples ({net_gain / len(results_df) * 100:.3f}% of set)")

    # Also print aggregate metrics for both, side by side
    from sklearn.metrics import precision_recall_fscore_support, accuracy_score
    clf_p, clf_r, clf_f1, _ = precision_recall_fscore_support(labels, results_df["classifier_pred"], average="binary", zero_division=0)
    fus_p, fus_r, fus_f1, _ = precision_recall_fscore_support(labels, results_df["fusion_pred"], average="binary", zero_division=0)
    print(f"\nClassifier alone : P={clf_p:.4f} R={clf_r:.4f} F1={clf_f1:.4f}")
    print(f"Fusion           : P={fus_p:.4f} R={fus_r:.4f} F1={fus_f1:.4f}")

    fixed_examples = results_df[(~results_df["classifier_correct"]) & (results_df["fusion_correct"])]
    print(f"\n--- Sample cases fusion FIXED (showing up to 5) ---")
    for _, row in fixed_examples.head(5).iterrows():
        print(f"Text: {row['text'][:90]} | true={row['label']} clf={row['classifier_score']:.2f} fusion={row['fusion_score']:.2f}")

    broke_examples = results_df[(results_df["classifier_correct"]) & (~results_df["fusion_correct"])]
    print(f"\n--- Sample cases fusion BROKE (showing up to 5) ---")
    for _, row in broke_examples.head(5).iterrows():
        print(f"Text: {row['text'][:90]} | true={row['label']} clf={row['classifier_score']:.2f} fusion={row['fusion_score']:.2f}")

    return results_df


def main():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Loading classifier on {device}...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR)
    model = AutoModelForSequenceClassification.from_pretrained(MODEL_DIR).to(device)
    model.eval()

    print("Loading semantic detector...")
    semantic = SemanticDetector(similarity_threshold=0.45)
    semantic.build_bank_from_csv("../data/train.csv")

    test_df = pd.read_csv("../data/test.csv")
    zero_day_df = pd.read_csv("../data/zero_day_test.csv")

    test_results = run_analysis(test_df, "FULL TEST SET (5625 rows)", tokenizer, model, semantic, device)
    test_results.to_csv("../data/error_analysis_test.csv", index=False)

    zero_day_results = run_analysis(zero_day_df, "ZERO-DAY HOLDOUT (92281 rows)", tokenizer, model, semantic, device)
    zero_day_results.to_csv("../data/error_analysis_zero_day.csv", index=False)

    print(f"\nSaved detailed results to ../data/error_analysis_test.csv and error_analysis_zero_day.csv")


if __name__ == "__main__":
    main()