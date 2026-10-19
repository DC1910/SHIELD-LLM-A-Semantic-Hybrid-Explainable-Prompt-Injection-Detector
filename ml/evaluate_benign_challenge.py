"""
evaluate_benign_challenge.py
============================
Phase 5A Evaluation – False-Positive Audit for SHIELD-LLM

Runs every prompt in data/benign_challenge.csv (all label=0, benign) through
each detector independently AND through the full FusionEngine, then reports
false-positive rates for each component.

THIS FILE IS READ-ONLY EVALUATION. It does not modify any model, threshold,
weight, rule, or pipeline component.

Run from the ml/ directory:
    python evaluate_benign_challenge.py

Or from the project root:
    python ml/evaluate_benign_challenge.py
"""

import sys
import os
import csv
import time
from collections import Counter, defaultdict

# ---------------------------------------------------------------------------
# Path setup – allow running from project root OR from ml/
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

# Make sure ml/ is on sys.path so that rules_engine / semantic_engine /
# fusion_engine can be imported regardless of where we are called from.
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

CHALLENGE_CSV = os.path.join(PROJECT_ROOT, "data", "benign_challenge.csv")
TRAIN_CSV = os.path.join(PROJECT_ROOT, "data", "train.csv")
OUTPUT_FAILURES_CSV = os.path.join(PROJECT_ROOT, "data", "benign_challenge_failures.csv")
FINAL_MODEL_DIR = os.path.join(SCRIPT_DIR, "final_model")

# ---------------------------------------------------------------------------
# Imports – use the existing, unmodified engines
# ---------------------------------------------------------------------------
print("=" * 70)
print("SHIELD-LLM  |  Phase 5A – Benign Challenge Evaluation")
print("=" * 70)
print()
print("[Setup] Importing detector modules …")

from rules_engine import check_rules           # noqa: E402
from semantic_engine import SemanticDetector    # noqa: E402
from fusion_engine import FusionEngine          # noqa: E402
import torch                                    # noqa: E402
from transformers import AutoTokenizer, AutoModelForSequenceClassification  # noqa: E402

# ---------------------------------------------------------------------------
# Load dataset
# ---------------------------------------------------------------------------
print(f"[Data] Loading challenge set from: {CHALLENGE_CSV}")
challenge_rows = []
with open(CHALLENGE_CSV, newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        challenge_rows.append(row)

total = len(challenge_rows)
print(f"[Data] Loaded {total} benign challenge prompts.\n")

category_counts = Counter(row["category"] for row in challenge_rows)
print("[Data] Category distribution:")
for cat, n in sorted(category_counts.items()):
    print(f"       {cat:<35} {n:>4} prompts")
print()

# ---------------------------------------------------------------------------
# 1. Rules Engine  (standalone)
# ---------------------------------------------------------------------------
print("=" * 70)
print("STEP 1 – Rules Engine (standalone)")
print("=" * 70)

rules_fp_rows = []
rules_fp_count = 0
rules_weight_total = 0.0
rules_category_fp_counter = Counter()

for row in challenge_rows:
    text = row["text"]
    result = check_rules(text)
    row["_rules_matched"] = result["matched"]
    row["_rules_max_weight"] = result["max_weight"]
    row["_rules_categories"] = ", ".join(result["categories"]) if result["categories"] else ""
    row["_rules_patterns"] = " | ".join(m["pattern"] for m in result["matches"]) if result["matches"] else ""

    if result["matched"]:
        rules_fp_count += 1
        rules_weight_total += result["max_weight"]
        rules_fp_rows.append(row)
        for cat in result["categories"]:
            rules_category_fp_counter[cat] += 1

rules_fpr = rules_fp_count / total
print(f"  Total benign examples : {total}")
print(f"  Flagged (FP)          : {rules_fp_count}")
print(f"  False-positive rate   : {rules_fpr:.1%}")
print(f"  Avg weight of FPs     : {rules_weight_total / max(rules_fp_count, 1):.3f}")
print(f"  Rule categories hit   : {dict(rules_category_fp_counter)}")
print()

# ---------------------------------------------------------------------------
# 2. DistilBERT Classifier (standalone)
# ---------------------------------------------------------------------------
print("=" * 70)
print("STEP 2 – DistilBERT Classifier (standalone)")
print("=" * 70)

device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"  Loading model from: {FINAL_MODEL_DIR}  (device={device})")
tokenizer = AutoTokenizer.from_pretrained(FINAL_MODEL_DIR)
clf_model = AutoModelForSequenceClassification.from_pretrained(FINAL_MODEL_DIR)
clf_model.to(device)
clf_model.eval()

CLASSIFIER_THRESHOLD = 0.50   # same gate used inside FusionEngine

clf_fp_count = 0
clf_scores = []

print("  Running classifier on all prompts …")
for row in challenge_rows:
    text = row["text"]
    inputs = tokenizer(text, truncation=True, padding="max_length",
                       max_length=128, return_tensors="pt")
    inputs = {k: v.to(device) for k, v in inputs.items()}
    with torch.no_grad():
        logits = clf_model(**inputs).logits
        probs = torch.softmax(logits, dim=-1)
    score = float(probs[0][1])
    row["_clf_score"] = score
    clf_scores.append(score)
    if score >= CLASSIFIER_THRESHOLD:
        clf_fp_count += 1

clf_fpr = clf_fp_count / total
print(f"  Total benign examples      : {total}")
print(f"  Flagged (score >= {CLASSIFIER_THRESHOLD:.2f})  : {clf_fp_count}")
print(f"  False-positive rate        : {clf_fpr:.1%}")
print(f"  Mean classifier score      : {sum(clf_scores) / len(clf_scores):.4f}")
print(f"  Max classifier score seen  : {max(clf_scores):.4f}")
print()

# ---------------------------------------------------------------------------
# 3. Semantic Detector (standalone)
# ---------------------------------------------------------------------------
print("=" * 70)
print("STEP 3 – Semantic Detector (standalone)")
print("=" * 70)

SEMANTIC_THRESHOLD = 0.45   # matches SemanticDetector default

detector = SemanticDetector(similarity_threshold=SEMANTIC_THRESHOLD)
detector.build_bank_from_csv(TRAIN_CSV)

sem_fp_count = 0
sem_scores = []

print("\n  Running semantic similarity on all prompts …")
sem_results = detector.check_batch([row["text"] for row in challenge_rows])

for row, sem_result in zip(challenge_rows, sem_results):
    row["_sem_score"] = sem_result["max_similarity"]
    row["_sem_closest"] = sem_result["closest_attack"]
    sem_scores.append(sem_result["max_similarity"])
    if sem_result["matched"]:
        sem_fp_count += 1

sem_fpr = sem_fp_count / total
print(f"  Total benign examples             : {total}")
print(f"  Flagged (similarity >= {SEMANTIC_THRESHOLD:.2f})      : {sem_fp_count}")
print(f"  False-positive rate               : {sem_fpr:.1%}")
print(f"  Mean similarity score             : {sum(sem_scores) / len(sem_scores):.4f}")
print(f"  Max similarity score seen         : {max(sem_scores):.4f}")
print()

# ---------------------------------------------------------------------------
# 4. FusionEngine (full pipeline)
# ---------------------------------------------------------------------------
print("=" * 70)
print("STEP 4 – Confidence-Gated FusionEngine (full pipeline)")
print("=" * 70)

print("  Initialising FusionEngine (reusing already-loaded model/detector) …")

# Build a minimal FusionEngine without re-loading from disk to save time.
# We monkey-patch the already-loaded tokenizer/model and semantic detector
# so we exercise the EXACT same logic without re-reading files.
engine = FusionEngine(
    model_dir=FINAL_MODEL_DIR,
    train_csv=TRAIN_CSV,
)
# Re-use already-loaded components to avoid double loading
engine.tokenizer = tokenizer
engine.model = clf_model
engine.device = device
engine.semantic_detector = detector
print("  FusionEngine ready (reused loaded components).\n")

fusion_safe = 0
fusion_suspicious = 0
fusion_malicious = 0
fusion_fp_count = 0   # FP = SUSPICIOUS or MALICIOUS (since all inputs are benign)

fusion_fp_by_mode = Counter()
fusion_fp_by_category = Counter()   # input category

all_fusion_results = []

print("  Running fusion analysis on all prompts …")
t0 = time.time()
for i, row in enumerate(challenge_rows):
    text = row["text"]
    result = engine.analyze(text)
    verdict = result["verdict"]
    row["_fusion_score"] = result["combined_score"]
    row["_fusion_mode"] = result["fusion_mode"]
    row["_fusion_verdict"] = verdict

    if verdict == "safe":
        fusion_safe += 1
    elif verdict == "suspicious":
        fusion_suspicious += 1
        fusion_fp_count += 1
        fusion_fp_by_mode[result["fusion_mode"]] += 1
        fusion_fp_by_category[row["category"]] += 1
    elif verdict == "malicious":
        fusion_malicious += 1
        fusion_fp_count += 1
        fusion_fp_by_mode[result["fusion_mode"]] += 1
        fusion_fp_by_category[row["category"]] += 1

    all_fusion_results.append(result)

    if (i + 1) % 50 == 0:
        elapsed = time.time() - t0
        print(f"    … processed {i+1}/{total} prompts ({elapsed:.1f}s elapsed)")

elapsed = time.time() - t0
print(f"  Done in {elapsed:.1f}s.\n")

fusion_fpr = fusion_fp_count / total
print(f"  Total benign examples : {total}")
print(f"  SAFE                  : {fusion_safe}")
print(f"  SUSPICIOUS (FP)       : {fusion_suspicious}")
print(f"  MALICIOUS  (FP)       : {fusion_malicious}")
print(f"  Total FPs             : {fusion_fp_count}")
print(f"  False-positive rate   : {fusion_fpr:.1%}")
print(f"  FP by fusion mode     : {dict(fusion_fp_by_mode)}")
print(f"  FP by input category  : {dict(fusion_fp_by_category)}")
print()

# ---------------------------------------------------------------------------
# 5. Save detailed failure rows
# ---------------------------------------------------------------------------
print("=" * 70)
print(f"STEP 5 – Saving failure details to: {OUTPUT_FAILURES_CSV}")
print("=" * 70)

# A row is a "failure" if ANY detector flagged it or fusion is not SAFE.
failure_rows = [
    row for row in challenge_rows
    if row.get("_rules_matched")
    or row.get("_clf_score", 0.0) >= CLASSIFIER_THRESHOLD
    or row.get("_sem_score", 0.0) >= SEMANTIC_THRESHOLD
    or row.get("_fusion_verdict", "safe") != "safe"
]

fieldnames = [
    "prompt",
    "category",
    "classifier_score",
    "clf_flagged",
    "semantic_score",
    "sem_flagged",
    "rules_matched",
    "rules_max_weight",
    "rules_categories",
    "rules_patterns",
    "fusion_score",
    "fusion_mode",
    "fusion_verdict",
]

with open(OUTPUT_FAILURES_CSV, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    for row in failure_rows:
        clf_score = row.get("_clf_score", 0.0)
        sem_score = row.get("_sem_score", 0.0)
        writer.writerow({
            "prompt": row["text"],
            "category": row["category"],
            "classifier_score": f"{clf_score:.4f}",
            "clf_flagged": "YES" if clf_score >= CLASSIFIER_THRESHOLD else "no",
            "semantic_score": f"{sem_score:.4f}",
            "sem_flagged": "YES" if sem_score >= SEMANTIC_THRESHOLD else "no",
            "rules_matched": "YES" if row.get("_rules_matched") else "no",
            "rules_max_weight": f"{row.get('_rules_max_weight', 0.0):.3f}",
            "rules_categories": row.get("_rules_categories", ""),
            "rules_patterns": row.get("_rules_patterns", ""),
            "fusion_score": f"{row.get('_fusion_score', 0.0):.4f}",
            "fusion_mode": row.get("_fusion_mode", ""),
            "fusion_verdict": row.get("_fusion_verdict", ""),
        })

print(f"  Saved {len(failure_rows)} rows to {OUTPUT_FAILURES_CSV}\n")

# ---------------------------------------------------------------------------
# 6. Top false-positive pattern analysis
# ---------------------------------------------------------------------------
print("=" * 70)
print("STEP 6 – Top False-Positive Pattern Analysis")
print("=" * 70)

# --- Rules FP breakdown ---
print("\n[Rules] Top false-positive categories (rules):")
for cat, cnt in rules_category_fp_counter.most_common():
    print(f"  {cat:<35} {cnt} FPs")

print("\n[Rules] Sample false-positive prompts (rules):")
for row in rules_fp_rows[:15]:
    print(f"  [{row['category']}] \"{row['text'][:80]}\"")
    print(f"    -> categories={row['_rules_categories']}, weight={row['_rules_max_weight']:.3f}")

# --- Semantic FP breakdown ---
sem_fp_rows = [r for r in challenge_rows if r.get("_sem_score", 0.0) >= SEMANTIC_THRESHOLD]
sem_fp_by_cat = Counter(r["category"] for r in sem_fp_rows)
print("\n[Semantic] False-positive categories (semantic):")
for cat, cnt in sem_fp_by_cat.most_common():
    print(f"  {cat:<35} {cnt} FPs")

print("\n[Semantic] Sample false-positive prompts (semantic, highest similarity first):")
sem_fp_rows_sorted = sorted(sem_fp_rows, key=lambda r: -r.get("_sem_score", 0.0))
for row in sem_fp_rows_sorted[:15]:
    print(f"  [{row['category']}] \"{row['text'][:80]}\"")
    print(f"    -> similarity={row['_sem_score']:.4f} | closest: \"{row['_sem_closest'][:60]}\"")

# --- Classifier FP rows ---
clf_fp_rows = [r for r in challenge_rows if r.get("_clf_score", 0.0) >= CLASSIFIER_THRESHOLD]
clf_fp_by_cat = Counter(r["category"] for r in clf_fp_rows)
print("\n[Classifier] False-positive categories (DistilBERT):")
for cat, cnt in clf_fp_by_cat.most_common():
    print(f"  {cat:<35} {cnt} FPs")

print("\n[Classifier] Sample false-positive prompts (highest score first):")
clf_fp_rows_sorted = sorted(clf_fp_rows, key=lambda r: -r.get("_clf_score", 0.0))
for row in clf_fp_rows_sorted[:15]:
    print(f"  [{row['category']}] \"{row['text'][:80]}\"  score={row['_clf_score']:.4f}")

# --- Fusion FP breakdown ---
fusion_fp_rows = [r for r in challenge_rows if r.get("_fusion_verdict", "safe") != "safe"]
fusion_fp_by_cat = Counter(r["category"] for r in fusion_fp_rows)
print("\n[Fusion] False-positive categories (FusionEngine):")
for cat, cnt in fusion_fp_by_cat.most_common():
    print(f"  {cat:<35} {cnt} FPs")

print("\n[Fusion] Sample false-positive prompts (highest fusion score first):")
fusion_fp_rows_sorted = sorted(fusion_fp_rows, key=lambda r: -r.get("_fusion_score", 0.0))
for row in fusion_fp_rows_sorted[:15]:
    print(f"  [{row['category']}] \"{row['text'][:80]}\"")
    print(f"    -> verdict={row['_fusion_verdict'].upper()}, score={row['_fusion_score']:.4f}, "
          f"mode={row['_fusion_mode']}, clf={row['_clf_score']:.4f}, "
          f"sem={row['_sem_score']:.4f}, rules={row['_rules_max_weight']:.3f}")

# ---------------------------------------------------------------------------
# 7. Final Summary
# ---------------------------------------------------------------------------
print()
print("=" * 70)
print("FINAL SUMMARY – Phase 5A Benign Challenge Evaluation")
print("=" * 70)

summary_rows = [
    ("Rules Engine",          rules_fp_count,  total, rules_fpr),
    ("DistilBERT Classifier", clf_fp_count,    total, clf_fpr),
    ("Semantic Detector",     sem_fp_count,    total, sem_fpr),
    ("FusionEngine (full)",   fusion_fp_count, total, fusion_fpr),
]

print(f"\n{'Component':<30} {'Total':>7} {'FPs':>7} {'FP Rate':>10}")
print("-" * 58)
for name, fp, tot, fpr in summary_rows:
    print(f"{name:<30} {tot:>7} {fp:>7}  {fpr:>8.1%}")

print()
print("[Fusion verdict breakdown]")
print(f"  SAFE       : {fusion_safe}")
print(f"  SUSPICIOUS : {fusion_suspicious}")
print(f"  MALICIOUS  : {fusion_malicious}")

# Determine primary source
fp_counts = {
    "Rules":      rules_fp_count,
    "DistilBERT": clf_fp_count,
    "Semantic":   sem_fp_count,
}
primary = max(fp_counts, key=fp_counts.get)

print()
print("[Primary FP Source Analysis]")
print(f"  Rules FP count    : {rules_fp_count}")
print(f"  DistilBERT FP cnt : {clf_fp_count}")
print(f"  Semantic FP count : {sem_fp_count}")
print(f"  -> Primary source  : ** {primary} ** (most standalone false positives)")

# Classify prompts with ONLY semantic FP (not clf or rules)
only_sem = [r for r in challenge_rows
            if r.get("_sem_score", 0.0) >= SEMANTIC_THRESHOLD
            and r.get("_clf_score", 0.0) < CLASSIFIER_THRESHOLD
            and not r.get("_rules_matched")]
only_clf = [r for r in challenge_rows
            if r.get("_clf_score", 0.0) >= CLASSIFIER_THRESHOLD
            and r.get("_sem_score", 0.0) < SEMANTIC_THRESHOLD
            and not r.get("_rules_matched")]
only_rules = [r for r in challenge_rows
              if r.get("_rules_matched")
              and r.get("_clf_score", 0.0) < CLASSIFIER_THRESHOLD
              and r.get("_sem_score", 0.0) < SEMANTIC_THRESHOLD]
multi_detector = [r for r in challenge_rows
                  if (
                      (r.get("_clf_score", 0.0) >= CLASSIFIER_THRESHOLD)
                      + (r.get("_sem_score", 0.0) >= SEMANTIC_THRESHOLD)
                      + (bool(r.get("_rules_matched")))
                  ) > 1]

print()
print("[Overlap Analysis – which detector is SOLELY responsible?]")
print(f"  Only semantic flagged (clf+rules benign)  : {len(only_sem)}")
print(f"  Only classifier flagged (sem+rules benign): {len(only_clf)}")
print(f"  Only rules flagged (clf+sem benign)       : {len(only_rules)}")
print(f"  Multiple detectors fired simultaneously   : {len(multi_detector)}")

print()
print("[Files created]")
print(f"  data/benign_challenge.csv          -> {total} benign evaluation prompts (EVAL-ONLY)")
print(f"  ml/evaluate_benign_challenge.py   -> this evaluation script")
print(f"  data/benign_challenge_failures.csv -> {len(failure_rows)} failure rows with full scores")

print()
print("=" * 70)
print("Phase 5A evaluation complete. Awaiting Phase 5B instructions.")
print("=" * 70)
