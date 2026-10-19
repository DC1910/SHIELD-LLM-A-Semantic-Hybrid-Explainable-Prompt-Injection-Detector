"""
train_hard_negative.py
======================
Phase 5B – Hard-Negative DistilBERT Retraining

Workflow
--------
1. Load original train.csv + val.csv (never modified).
2. Load data/hard_negative_benign.csv and verify NO overlap with benign_challenge.csv.
3. Build augmented training CSV (original + hard-negatives) and report class balance.
4. Fine-tune a NEW DistilBERT candidate using the same hyper-parameters as the
   original train_model.py run.  Saves to ml/models/distilbert_hard_negative/.
5. Evaluate OLD vs NEW on:
     A. test.csv        – precision / recall / F1 / FP / FN / ROC-AUC / PR-AUC
     B. zero_day_test.csv – attack recall
     C. benign_challenge.csv – false-positive rate
   Per-category FP breakdown for the challenge set.
6. Print a side-by-side comparison table and recommendation.

IMPORTANT: final_model/ is NEVER touched.

Run from ml/ directory:
    python train_hard_negative.py
"""

import os
import sys
import time
import csv

import numpy as np
import pandas as pd
import torch
from datasets import Dataset
from sklearn.metrics import (
    accuracy_score,
    precision_recall_fscore_support,
    roc_auc_score,
    average_precision_score,
    confusion_matrix,
)
from transformers import (
    AutoTokenizer,
    AutoModelForSequenceClassification,
    TrainingArguments,
    Trainer,
)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR   = os.path.join(SCRIPT_DIR, "..", "data")

TRAIN_CSV        = os.path.join(DATA_DIR, "train.csv")
VAL_CSV          = os.path.join(DATA_DIR, "val.csv")
TEST_CSV         = os.path.join(DATA_DIR, "test.csv")
ZERO_DAY_CSV     = os.path.join(DATA_DIR, "zero_day_test.csv")
CHALLENGE_CSV    = os.path.join(DATA_DIR, "benign_challenge.csv")
HARD_NEG_CSV     = os.path.join(DATA_DIR, "hard_negative_benign.csv")
AUGMENTED_CSV    = os.path.join(DATA_DIR, "train_augmented.csv")   # written here, never replaces train.csv

OLD_MODEL_DIR    = os.path.join(SCRIPT_DIR, "final_model")
NEW_MODEL_DIR    = os.path.join(SCRIPT_DIR, "models", "distilbert_hard_negative")
CHECKPOINT_DIR   = os.path.join(SCRIPT_DIR, "models", "distilbert_hard_negative_ckpt")

# Same hyper-parameters as original train_model.py
MODEL_NAME       = "distilbert-base-uncased"
MAX_LENGTH       = 128
NUM_EPOCHS       = 4
BATCH_SIZE       = 8
GRAD_ACCUM       = 4       # effective batch = 32
LEARNING_RATE    = 2e-5
WEIGHT_DECAY     = 0.01
CLASSIFIER_THRESHOLD = 0.50

# Zero-day evaluation is expensive (92 k rows) – cap for speed
ZERO_DAY_SAMPLE  = 5000
RANDOM_SEED      = 42

os.makedirs(NEW_MODEL_DIR, exist_ok=True)
os.makedirs(CHECKPOINT_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def banner(msg):
    print(f"\n{'='*70}")
    print(msg)
    print('='*70)


def score_model(tokenizer, model, device, texts, batch_size=64):
    """Return malicious-class probability for each text in `texts`."""
    model.eval()
    all_probs = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i+batch_size]
        enc = tokenizer(
            batch,
            truncation=True,
            padding="max_length",
            max_length=MAX_LENGTH,
            return_tensors="pt",
        )
        enc = {k: v.to(device) for k, v in enc.items()}
        with torch.no_grad():
            logits = model(**enc).logits
            probs  = torch.softmax(logits, dim=-1)[:, 1].cpu().numpy()
        all_probs.extend(probs.tolist())
    return np.array(all_probs)


def full_metrics(labels, probs, threshold=CLASSIFIER_THRESHOLD, name=""):
    preds = (probs >= threshold).astype(int)
    acc   = accuracy_score(labels, preds)
    prec, rec, f1, _ = precision_recall_fscore_support(
        labels, preds, average="binary", zero_division=0
    )
    cm  = confusion_matrix(labels, preds, labels=[0, 1])
    tn, fp, fn, tp = cm.ravel()
    roc = roc_auc_score(labels, probs)
    pr  = average_precision_score(labels, probs)
    return {
        "name": name, "acc": acc, "prec": prec, "rec": rec, "f1": f1,
        "fp": int(fp), "fn": int(fn), "tp": int(tp), "tn": int(tn),
        "roc_auc": roc, "pr_auc": pr,
    }


def print_metrics(m):
    print(f"  Accuracy  : {m['acc']:.4f}")
    print(f"  Precision : {m['prec']:.4f}")
    print(f"  Recall    : {m['rec']:.4f}")
    print(f"  F1        : {m['f1']:.4f}")
    print(f"  FP        : {m['fp']}   FN : {m['fn']}")
    print(f"  ROC-AUC   : {m['roc_auc']:.4f}")
    print(f"  PR-AUC    : {m['pr_auc']:.4f}")


# ---------------------------------------------------------------------------
# 0. Sanity-check: no challenge prompt leaked into hard-negative set
# ---------------------------------------------------------------------------
banner("STEP 0 – Overlap Guard: challenge vs hard-negative")

challenge_df = pd.read_csv(CHALLENGE_CSV)
hard_neg_df  = pd.read_csv(HARD_NEG_CSV)

challenge_texts = set(challenge_df["text"].str.strip().str.lower())
hard_neg_texts  = set(hard_neg_df["text"].str.strip().str.lower())

overlap = challenge_texts & hard_neg_texts
if overlap:
    print(f"  WARNING: {len(overlap)} overlapping prompts found – removing from hard-negative set.")
    hard_neg_df = hard_neg_df[
        ~hard_neg_df["text"].str.strip().str.lower().isin(overlap)
    ].reset_index(drop=True)
else:
    print(f"  OK – no overlap. Hard-negative set has {len(hard_neg_df)} unique prompts.")

# ---------------------------------------------------------------------------
# 1. Build augmented training dataset
# ---------------------------------------------------------------------------
banner("STEP 1 – Build Augmented Training Dataset")

train_df = pd.read_csv(TRAIN_CSV)
print(f"  Original train.csv   : {len(train_df):>7} rows")
print(f"    label=0 (benign)   : {(train_df.label==0).sum():>7}")
print(f"    label=1 (malicious): {(train_df.label==1).sum():>7}")

# Upsample hard-negatives to add meaningful weight without overwhelming balance.
# Strategy: duplicate them enough so they are ~5% of the total benign class.
orig_benign   = (train_df.label == 0).sum()
orig_malicious = (train_df.label == 1).sum()
target_hn_count = max(len(hard_neg_df), int(orig_benign * 0.05))
# How many times to repeat the hard-neg set to reach target
repeat = max(1, int(np.ceil(target_hn_count / len(hard_neg_df))))
hn_expanded = pd.concat([hard_neg_df] * repeat, ignore_index=True).head(target_hn_count)
hn_expanded = hn_expanded[["text", "label", "source"]]

# Ensure original train_df has a source column
if "source" not in train_df.columns:
    train_df["source"] = "original_train"

aug_df = pd.concat(
    [train_df[["text", "label", "source"]], hn_expanded],
    ignore_index=True
).sample(frac=1, random_state=RANDOM_SEED).reset_index(drop=True)

new_benign    = (aug_df.label == 0).sum()
new_malicious = (aug_df.label == 1).sum()
ratio = new_malicious / new_benign

print(f"\n  Hard-negatives added : {len(hn_expanded):>7}  (repeated {repeat}x from {len(hard_neg_df)} unique)")
print(f"\n  Augmented dataset    : {len(aug_df):>7} rows")
print(f"    label=0 (benign)   : {new_benign:>7}")
print(f"    label=1 (malicious): {new_malicious:>7}")
print(f"    malicious/benign   : {ratio:.3f}x  (original was {orig_malicious/orig_benign:.3f}x)")

if ratio > 2.5:
    print("  WARNING: Ratio >2.5 – consider adding more hard negatives.")
elif ratio < 0.8:
    print("  WARNING: Ratio <0.8 – benign class now dominates heavily.")
else:
    print("  Class balance is acceptable.")

aug_df[["text", "label"]].to_csv(AUGMENTED_CSV, index=False)
print(f"\n  Saved to: {AUGMENTED_CSV}")

# ---------------------------------------------------------------------------
# 2. Tokenise
# ---------------------------------------------------------------------------
banner("STEP 2 – Tokenise")

device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"  Device: {device}")
if device == "cuda":
    print(f"  GPU   : {torch.cuda.get_device_name(0)}")

print(f"  Loading tokenizer: {MODEL_NAME}")
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)

val_df = pd.read_csv(VAL_CSV)

def to_hf_dataset(df):
    ds = Dataset.from_pandas(df[["text", "label"]].reset_index(drop=True))
    def tok(batch):
        return tokenizer(batch["text"], truncation=True,
                         padding="max_length", max_length=MAX_LENGTH)
    ds = ds.map(tok, batched=True)
    ds = ds.rename_column("label", "labels")
    ds.set_format(type="torch", columns=["input_ids", "attention_mask", "labels"])
    return ds

print("  Tokenising augmented train set …")
train_ds = to_hf_dataset(aug_df)
print("  Tokenising validation set …")
val_ds   = to_hf_dataset(val_df)
print(f"  Train tokens: {len(train_ds)} | Val tokens: {len(val_ds)}")

# ---------------------------------------------------------------------------
# 3. Train
# ---------------------------------------------------------------------------
banner("STEP 3 – Training New DistilBERT Candidate")

def compute_metrics(eval_pred):
    logits, labels = eval_pred
    preds = np.argmax(logits, axis=-1)
    acc = accuracy_score(labels, preds)
    prec, rec, f1, _ = precision_recall_fscore_support(
        labels, preds, average="binary", zero_division=0
    )
    return {"accuracy": acc, "precision": prec, "recall": rec, "f1": f1}

model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME, num_labels=2)

training_args = TrainingArguments(
    output_dir=CHECKPOINT_DIR,
    num_train_epochs=NUM_EPOCHS,
    per_device_train_batch_size=BATCH_SIZE,
    per_device_eval_batch_size=BATCH_SIZE,
    gradient_accumulation_steps=GRAD_ACCUM,
    learning_rate=LEARNING_RATE,
    weight_decay=WEIGHT_DECAY,
    eval_strategy="epoch",
    save_strategy="epoch",
    save_total_limit=2,
    load_best_model_at_end=True,
    metric_for_best_model="f1",
    logging_dir=os.path.join(CHECKPOINT_DIR, "logs"),
    logging_steps=100,
    fp16=(device == "cuda"),
    report_to="none",
)

trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=train_ds,
    eval_dataset=val_ds,
    compute_metrics=compute_metrics,
)

t0 = time.time()
trainer.train()
elapsed = time.time() - t0
print(f"\n  Training complete in {elapsed/60:.1f} min.")

print(f"\n  Saving new model to: {NEW_MODEL_DIR}")
trainer.save_model(NEW_MODEL_DIR)
tokenizer.save_pretrained(NEW_MODEL_DIR)
print("  Saved.")

# ---------------------------------------------------------------------------
# 4. Load models for evaluation
# ---------------------------------------------------------------------------
banner("STEP 4 – Loading Both Models for Evaluation")

print(f"  Loading OLD model from: {OLD_MODEL_DIR}")
old_tokenizer = AutoTokenizer.from_pretrained(OLD_MODEL_DIR)
old_model     = AutoModelForSequenceClassification.from_pretrained(OLD_MODEL_DIR).to(device)
old_model.eval()

print(f"  Loading NEW model from: {NEW_MODEL_DIR}")
new_tokenizer = AutoTokenizer.from_pretrained(NEW_MODEL_DIR)
new_model     = AutoModelForSequenceClassification.from_pretrained(NEW_MODEL_DIR).to(device)
new_model.eval()
print("  Both models ready.")

# ---------------------------------------------------------------------------
# 5A. Evaluate on held-out test.csv
# ---------------------------------------------------------------------------
banner("STEP 5A – Held-Out test.csv Evaluation")

test_df = pd.read_csv(TEST_CSV)
test_texts  = test_df["text"].astype(str).tolist()
test_labels = test_df["label"].tolist()

print(f"  Scoring OLD on {len(test_df)} test rows …")
old_test_probs = score_model(old_tokenizer, old_model, device, test_texts)
print(f"  Scoring NEW on {len(test_df)} test rows …")
new_test_probs = score_model(new_tokenizer, new_model, device, test_texts)

old_test = full_metrics(test_labels, old_test_probs, name="OLD – test.csv")
new_test = full_metrics(test_labels, new_test_probs, name="NEW – test.csv")

print("\n  [OLD model – test.csv]")
print_metrics(old_test)
print("\n  [NEW model – test.csv]")
print_metrics(new_test)

# ---------------------------------------------------------------------------
# 5B. Evaluate on zero_day_test.csv (attack recall only)
# ---------------------------------------------------------------------------
banner("STEP 5B – Zero-Day Attack Recall")

zd_df = pd.read_csv(ZERO_DAY_CSV)
# Use a random sample for speed
zd_sample = zd_df.sample(n=min(ZERO_DAY_SAMPLE, len(zd_df)),
                          random_state=RANDOM_SEED)
zd_texts  = zd_sample["text"].astype(str).tolist()
zd_labels = zd_sample["label"].tolist()   # all 1s

print(f"  Zero-day sample: {len(zd_sample)} rows (of {len(zd_df)} total, all label=1)")

print("  Scoring OLD …")
old_zd_probs = score_model(old_tokenizer, old_model, device, zd_texts)
print("  Scoring NEW …")
new_zd_probs = score_model(new_tokenizer, new_model, device, zd_texts)

old_zd_preds = (old_zd_probs >= CLASSIFIER_THRESHOLD).astype(int)
new_zd_preds = (new_zd_probs >= CLASSIFIER_THRESHOLD).astype(int)

old_zd_detected = int(old_zd_preds.sum())
new_zd_detected = int(new_zd_preds.sum())
old_zd_missed   = len(zd_sample) - old_zd_detected
new_zd_missed   = len(zd_sample) - new_zd_detected
old_zd_recall   = old_zd_detected / len(zd_sample)
new_zd_recall   = new_zd_detected / len(zd_sample)

print(f"\n  [OLD] detected={old_zd_detected}  missed={old_zd_missed}  recall={old_zd_recall:.4f}")
print(f"  [NEW] detected={new_zd_detected}  missed={new_zd_missed}  recall={new_zd_recall:.4f}")

# ---------------------------------------------------------------------------
# 5C. Evaluate on frozen benign_challenge.csv
# ---------------------------------------------------------------------------
banner("STEP 5C – Benign Challenge False-Positive Rate")

challenge_df = pd.read_csv(CHALLENGE_CSV)
ch_texts     = challenge_df["text"].astype(str).tolist()
ch_categories = challenge_df["category"].tolist()
ch_total      = len(challenge_df)

print(f"  Challenge set: {ch_total} benign prompts")

print("  Scoring OLD …")
old_ch_probs = score_model(old_tokenizer, old_model, device, ch_texts)
print("  Scoring NEW …")
new_ch_probs = score_model(new_tokenizer, new_model, device, ch_texts)

old_ch_preds = (old_ch_probs >= CLASSIFIER_THRESHOLD).astype(int)
new_ch_preds = (new_ch_probs >= CLASSIFIER_THRESHOLD).astype(int)

old_fp = int(old_ch_preds.sum())
new_fp = int(new_ch_preds.sum())
old_fpr = old_fp / ch_total
new_fpr = new_fp / ch_total

print(f"\n  [OLD] FP={old_fp}  FPR={old_fpr:.1%}")
print(f"  [NEW] FP={new_fp}  FPR={new_fpr:.1%}")

# Per-category breakdown
from collections import Counter, defaultdict

old_fp_by_cat = Counter()
new_fp_by_cat = Counter()
cat_counts    = Counter(ch_categories)

for pred_old, pred_new, cat in zip(old_ch_preds, new_ch_preds, ch_categories):
    if pred_old:
        old_fp_by_cat[cat] += 1
    if pred_new:
        new_fp_by_cat[cat] += 1

print("\n  [Per-Category FP comparison]")
print(f"  {'Category':<35} {'Total':>6}  {'OLD FP':>7} {'OLD%':>6}  {'NEW FP':>7} {'NEW%':>6}")
print("  " + "-"*73)
for cat in sorted(cat_counts.keys()):
    n = cat_counts[cat]
    o = old_fp_by_cat[cat]
    nw = new_fp_by_cat[cat]
    print(f"  {cat:<35} {n:>6}  {o:>7} {o/n:>5.1%}   {nw:>7} {nw/n:>5.1%}")
print("  " + "-"*73)
print(f"  {'TOTAL':<35} {ch_total:>6}  {old_fp:>7} {old_fpr:>5.1%}   {new_fp:>7} {new_fpr:>5.1%}")

# ---------------------------------------------------------------------------
# 6. Per-category challenge detail (known failures, short, edu, cyber)
# ---------------------------------------------------------------------------
banner("STEP 6 – Specific Category Deep-Dive")

target_cats = [
    "short_prompts",
    "cybersecurity_terminology",
    "prompt_injection_education",
    "known_failures",
    "quoted_attack_phrases",
    "benign_attack_discussion",
]

for cat in target_cats:
    idxs = [i for i, c in enumerate(ch_categories) if c == cat]
    if not idxs:
        continue
    o_fp = sum(old_ch_preds[i] for i in idxs)
    n_fp = sum(new_ch_preds[i] for i in idxs)
    n_tot = len(idxs)
    print(f"  {cat:<35}  n={n_tot:>4}  OLD FP={o_fp} ({o_fp/n_tot:.0%})  "
          f"NEW FP={n_fp} ({n_fp/n_tot:.0%})  "
          f"delta={o_fp-n_fp:+d}")

# Worst remaining FPs after retraining
print("\n  [NEW model – remaining false positives on challenge set (score desc)]")
remaining_fp_rows = [
    (ch_texts[i], cat, float(new_ch_probs[i]))
    for i, cat in enumerate(ch_categories)
    if new_ch_preds[i] == 1
]
remaining_fp_rows.sort(key=lambda x: -x[2])
for prompt, cat, score in remaining_fp_rows[:20]:
    print(f"    [{cat}] \"{prompt[:75]}\"  score={score:.4f}")

# ---------------------------------------------------------------------------
# 7. Final comparison table + recommendation
# ---------------------------------------------------------------------------
banner("STEP 7 – OLD vs NEW Comparison Table & Recommendation")

def delta(new, old, higher_better=True):
    d = new - old
    sign = "+" if d >= 0 else ""
    arrow = "^" if (d > 0 and higher_better) or (d < 0 and not higher_better) else "v"
    return f"{sign}{d:.4f} {arrow}"

print(f"""
  ┌{'─'*58}┐
  │ Metric                    │   OLD       │   NEW       │
  ├{'─'*58}┤
  │ === HELD-OUT TEST.CSV =====================          │
  │ Precision                 │ {old_test['prec']:.4f}      │ {new_test['prec']:.4f}      │
  │ Recall                    │ {old_test['rec']:.4f}      │ {new_test['rec']:.4f}      │
  │ F1                        │ {old_test['f1']:.4f}      │ {new_test['f1']:.4f}      │
  │ FP (benign flagged)       │ {old_test['fp']:>5}       │ {new_test['fp']:>5}       │
  │ FN (attacks missed)       │ {old_test['fn']:>5}       │ {new_test['fn']:>5}       │
  │ ROC-AUC                   │ {old_test['roc_auc']:.4f}      │ {new_test['roc_auc']:.4f}      │
  │ PR-AUC                    │ {old_test['pr_auc']:.4f}      │ {new_test['pr_auc']:.4f}      │
  ├{'─'*58}┤
  │ === ZERO-DAY (sampled {ZERO_DAY_SAMPLE}) =========================│
  │ Attacks detected          │ {old_zd_detected:>5}       │ {new_zd_detected:>5}       │
  │ Attacks missed            │ {old_zd_missed:>5}       │ {new_zd_missed:>5}       │
  │ Attack recall             │ {old_zd_recall:.4f}      │ {new_zd_recall:.4f}      │
  ├{'─'*58}┤
  │ === BENIGN CHALLENGE (n={ch_total}) ========================│
  │ False positives           │ {old_fp:>5}       │ {new_fp:>5}       │
  │ False-positive rate       │ {old_fpr:.1%}      │ {new_fpr:.1%}      │
  └{'─'*58}┘
""")

# Recommendation
fp_reduction   = old_fp - new_fp
fp_reduction_pct = fp_reduction / max(old_fp, 1) * 100
f1_delta       = new_test['f1'] - old_test['f1']
zd_delta       = new_zd_recall - old_zd_recall
FP_THRESHOLD   = 0.30   # >30% FP reduction is "substantial"
PERF_TOLERANCE = 0.01   # F1 drop ≤ 1% is acceptable

print("  [Recommendation]")
substantial_fp = fp_reduction_pct >= FP_THRESHOLD * 100
preserved_f1   = f1_delta >= -PERF_TOLERANCE
preserved_zd   = zd_delta >= -PERF_TOLERANCE

print(f"  FP reduction       : {fp_reduction:+d} ({fp_reduction_pct:+.1f}%)  "
      f"{'SUBSTANTIAL' if substantial_fp else 'MODEST'}")
print(f"  test.csv F1 delta  : {f1_delta:+.4f}  "
      f"{'OK' if preserved_f1 else 'DEGRADED'}")
print(f"  Zero-day recall delta: {zd_delta:+.4f}  "
      f"{'OK' if preserved_zd else 'DEGRADED'}")

if substantial_fp and preserved_f1 and preserved_zd:
    verdict = "APPROVE – New model substantially reduces false positives while preserving performance."
elif substantial_fp and not preserved_f1:
    verdict = "REVIEW – FP reduction achieved but test F1 degraded beyond tolerance. Review before promoting."
elif not substantial_fp:
    verdict = "INSUFFICIENT – FP reduction is modest. Additional hard-negative data or threshold tuning may be needed."
else:
    verdict = "REVIEW – Mixed results. Manual inspection recommended before promoting."

print(f"\n  VERDICT: {verdict}")
print()
print("  NOTE: ml/final_model/ was NOT touched. Candidate is at:")
print(f"        {NEW_MODEL_DIR}")
print()
print("  Awaiting Phase 5B approval before replacing production model.")
print()
banner("Phase 5B Complete – Awaiting Instructions")
