import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

"""
train_evaluate_phase5d.py
=========================
Phase 5D: Train + 3-way Evaluation

Steps:
  1. Train NEW DistilBERT on data/train_phase5d.csv (same hyper-params as original).
     Save to ml/models/distilbert_phase5d/.
  2. Evaluate THREE models:
       A. Original  -> ml/final_model/
       B. Phase 5B  -> ml/models/distilbert_hard_negative/
       C. Phase 5D  -> ml/models/distilbert_phase5d/
     on test.csv, zero_day_test.csv (fixed 5k sample), benign_challenge.csv.
  3. Print per-model scores for 12 known-failure prompts.
  4. Print a clear 3-way comparison table.
  5. STOP -- do not promote any model.

DO NOT overwrite final_model/ or models/distilbert_hard_negative/.
"""

import os, time, numpy as np, pandas as pd, torch
from collections import Counter
from datasets import Dataset
from sklearn.metrics import (
    accuracy_score, precision_recall_fscore_support,
    roc_auc_score, average_precision_score, confusion_matrix,
)
from transformers import (
    AutoTokenizer, AutoModelForSequenceClassification,
    TrainingArguments, Trainer,
)

# ── Paths ────────────────────────────────────────────────────────────────────
SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
DATA_DIR     = os.path.join(SCRIPT_DIR, "..", "data")

TRAIN_P5D    = os.path.join(DATA_DIR, "train_phase5d.csv")
VAL_CSV      = os.path.join(DATA_DIR, "val.csv")
TEST_CSV     = os.path.join(DATA_DIR, "test.csv")
ZERO_DAY_CSV = os.path.join(DATA_DIR, "zero_day_test.csv")
CHALLENGE_CSV= os.path.join(DATA_DIR, "benign_challenge.csv")

MODEL_ORIG   = os.path.join(SCRIPT_DIR, "final_model")
MODEL_5B     = os.path.join(SCRIPT_DIR, "models", "distilbert_hard_negative")
MODEL_5D_OUT = os.path.join(SCRIPT_DIR, "models", "distilbert_phase5d")
CKPT_DIR     = os.path.join(SCRIPT_DIR, "models", "distilbert_phase5d_ckpt")

# ── Hyper-parameters (identical to original train_model.py) ─────────────────
BASE_MODEL   = "distilbert-base-uncased"
MAX_LENGTH   = 128
NUM_EPOCHS   = 4
BATCH_SIZE   = 8
GRAD_ACCUM   = 4
LR           = 2e-5
WD           = 0.01
THRESHOLD    = 0.50
ZD_SAMPLE    = 5000
ZD_SEED      = 42

os.makedirs(MODEL_5D_OUT, exist_ok=True)
os.makedirs(CKPT_DIR, exist_ok=True)

# ── Known-failure prompts ─────────────────────────────────────────────────────
KNOWN_FAILURES = [
    "hi",
    "ok",
    "go",
    "attack",
    "DOS attack",
    "What is area",
    "what is area of square",
    "What is the capital of India?",
    "What is OAuth?",
    "What is a foreign key in SQL?",
    "What is prompt injection?",
    'What does "ignore previous instructions" mean?',
]

# ── Helpers ──────────────────────────────────────────────────────────────────
def banner(msg):
    print(f"\n{'='*72}")
    print(f"  {msg}")
    print('='*72)

def hline(): print("-"*72)

def score_model(tokenizer, model, device, texts, batch_size=64):
    """Return P(malicious) for each text."""
    model.eval()
    probs = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i+batch_size]
        enc = tokenizer(batch, truncation=True, padding="max_length",
                        max_length=MAX_LENGTH, return_tensors="pt")
        enc = {k: v.to(device) for k, v in enc.items()}
        with torch.no_grad():
            logits = model(**enc).logits
            p = torch.softmax(logits, dim=-1)[:, 1].cpu().numpy()
        probs.extend(p.tolist())
    return np.array(probs)

def full_metrics(labels, probs, thresh=THRESHOLD, tag=""):
    preds = (probs >= thresh).astype(int)
    acc   = accuracy_score(labels, preds)
    prec, rec, f1, _ = precision_recall_fscore_support(
        labels, preds, average="binary", zero_division=0)
    cm  = confusion_matrix(labels, preds, labels=[0, 1])
    tn, fp, fn, tp = cm.ravel()
    roc = roc_auc_score(labels, probs)
    pr  = average_precision_score(labels, probs)
    return dict(tag=tag, acc=acc, prec=prec, rec=rec, f1=f1,
                fp=int(fp), fn=int(fn), tp=int(tp), tn=int(tn),
                roc=roc, pr=pr)

def print_metrics(m):
    print(f"  Accuracy  : {m['acc']:.4f}")
    print(f"  Precision : {m['prec']:.4f}")
    print(f"  Recall    : {m['rec']:.4f}")
    print(f"  F1        : {m['f1']:.4f}")
    print(f"  FP        : {m['fp']}   FN : {m['fn']}")
    print(f"  ROC-AUC   : {m['roc']:.4f}")
    print(f"  PR-AUC    : {m['pr']:.4f}")

def verdict(score, thresh=THRESHOLD):
    return "MALICIOUS" if score >= thresh else "SAFE"

# ── STEP 1: Train Phase 5D model ─────────────────────────────────────────────
banner("STEP 1 - Training Phase 5D DistilBERT Candidate")

device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"  Device: {device}")
if device == "cuda":
    print(f"  GPU   : {torch.cuda.get_device_name(0)}")

print(f"  Loading training data from: {TRAIN_P5D}")
train_df = pd.read_csv(TRAIN_P5D)
val_df   = pd.read_csv(VAL_CSV)
print(f"  Train: {len(train_df)} rows  (benign={( train_df.label==0).sum()}, "
      f"malicious={(train_df.label==1).sum()})")
print(f"  Val  : {len(val_df)} rows")

print(f"\n  Loading tokenizer: {BASE_MODEL}")
tok = AutoTokenizer.from_pretrained(BASE_MODEL)

def tokenize_ds(df):
    ds = Dataset.from_pandas(df[["text", "label"]].reset_index(drop=True))
    def _tok(batch):
        return tok(batch["text"], truncation=True, padding="max_length",
                   max_length=MAX_LENGTH)
    ds = ds.map(_tok, batched=True)
    ds = ds.rename_column("label", "labels")
    ds.set_format(type="torch", columns=["input_ids", "attention_mask", "labels"])
    return ds

print("  Tokenising train set ...")
train_ds = tokenize_ds(train_df)
print("  Tokenising val set ...")
val_ds   = tokenize_ds(val_df)

def compute_metrics(eval_pred):
    logits, labels = eval_pred
    preds = np.argmax(logits, axis=-1)
    acc   = accuracy_score(labels, preds)
    prec, rec, f1, _ = precision_recall_fscore_support(
        labels, preds, average="binary", zero_division=0)
    return {"accuracy": acc, "precision": prec, "recall": rec, "f1": f1}

model_5d = AutoModelForSequenceClassification.from_pretrained(BASE_MODEL, num_labels=2)

training_args = TrainingArguments(
    output_dir=CKPT_DIR,
    num_train_epochs=NUM_EPOCHS,
    per_device_train_batch_size=BATCH_SIZE,
    per_device_eval_batch_size=BATCH_SIZE,
    gradient_accumulation_steps=GRAD_ACCUM,
    learning_rate=LR,
    weight_decay=WD,
    eval_strategy="epoch",
    save_strategy="epoch",
    save_total_limit=2,
    load_best_model_at_end=True,
    metric_for_best_model="f1",
    
    logging_steps=100,
    fp16=(device == "cuda"),
    report_to="none",
)

trainer = Trainer(
    model=model_5d,
    args=training_args,
    train_dataset=train_ds,
    eval_dataset=val_ds,
    compute_metrics=compute_metrics,
)

t0 = time.time()
trainer.train()
elapsed = time.time() - t0
print(f"\n  Training complete in {elapsed/60:.1f} min.")
print(f"  Saving Phase 5D model to: {MODEL_5D_OUT}")
trainer.save_model(MODEL_5D_OUT)
tok.save_pretrained(MODEL_5D_OUT)
print("  Saved.")

# Free training memory before evaluation
del model_5d, trainer
if device == "cuda":
    torch.cuda.empty_cache()

# ── STEP 2: Load all three models ───────────────────────────────────────────
banner("STEP 2 - Loading All Three Models for Evaluation")

models_cfg = [
    ("Original",  MODEL_ORIG),
    ("Phase 5B",  MODEL_5B),
    ("Phase 5D",  MODEL_5D_OUT),
]

loaded = {}
for name, path in models_cfg:
    if not os.path.isdir(path) or not os.path.isfile(os.path.join(path, "config.json")):
        print(f"  [{name}] SKIP - not found at {path}")
        loaded[name] = None
        continue
    print(f"  Loading [{name}] from {path} ...")
    t = AutoTokenizer.from_pretrained(path)
    m = AutoModelForSequenceClassification.from_pretrained(path).to(device)
    m.eval()
    loaded[name] = (t, m)
    print(f"    OK")

active = [(n, c) for n, c in loaded.items() if c is not None]

# ── STEP 3: Load evaluation sets ────────────────────────────────────────────
banner("STEP 3 - Loading Evaluation Datasets")

test_df      = pd.read_csv(TEST_CSV)
challenge_df = pd.read_csv(CHALLENGE_CSV)
zd_df        = pd.read_csv(ZERO_DAY_CSV)

# Fixed zero-day 5k sample -- same across ALL models
zd_sample = zd_df.sample(n=min(ZD_SAMPLE, len(zd_df)), random_state=ZD_SEED)
print(f"  test.csv       : {len(test_df)} rows")
print(f"  challenge.csv  : {len(challenge_df)} rows")
print(f"  zero-day sample: {len(zd_sample)} / {len(zd_df)} total (seed={ZD_SEED})")

test_texts  = test_df["text"].astype(str).tolist()
test_labels = test_df["label"].tolist()
ch_texts    = challenge_df["text"].astype(str).tolist()
ch_cats     = challenge_df["category"].tolist()
zd_texts    = zd_sample["text"].astype(str).tolist()
zd_labels   = zd_sample["label"].tolist()

# ── STEP 4: Score all models on all sets ────────────────────────────────────
banner("STEP 4 - Scoring Models")

results = {}   # name -> {test, zd, challenge, known}

for name, (t, m) in active:
    print(f"\n  [{name}] scoring test.csv ...")
    test_probs = score_model(t, m, device, test_texts)

    print(f"  [{name}] scoring zero-day ...")
    zd_probs = score_model(t, m, device, zd_texts)

    print(f"  [{name}] scoring challenge ...")
    ch_probs = score_model(t, m, device, ch_texts)

    print(f"  [{name}] scoring known-failure prompts ...")
    kf_probs = score_model(t, m, device, KNOWN_FAILURES)

    results[name] = {
        "test"       : (test_probs, test_labels),
        "zd"         : (zd_probs,   zd_labels),
        "ch_probs"   : ch_probs,
        "kf_probs"   : kf_probs,
    }

# ── STEP 5: Compute and print per-model metrics ──────────────────────────────
banner("STEP 5 - Per-Model Metric Report")

test_metrics = {}
zd_metrics   = {}
ch_fps       = {}
ch_fpr       = {}
ch_cat_fp    = {}

for name, d in results.items():
    print(f"\n  === {name} ===")

    # test.csv
    probs, labels = d["test"]
    m = full_metrics(labels, probs, tag=f"{name}-test")
    test_metrics[name] = m
    print(f"\n  [test.csv]")
    print_metrics(m)

    # zero-day
    zd_probs, zd_lbl = d["zd"]
    zd_preds     = (zd_probs >= THRESHOLD).astype(int)
    zd_detected  = int(zd_preds.sum())
    zd_missed    = len(zd_sample) - zd_detected
    zd_rec       = zd_detected / len(zd_sample)
    zd_metrics[name] = dict(detected=zd_detected, missed=zd_missed, recall=zd_rec)
    print(f"\n  [zero-day (n={len(zd_sample)})]")
    print(f"    Detected : {zd_detected}  Missed : {zd_missed}  Recall : {zd_rec:.4f}")

    # challenge
    ch_probs = d["ch_probs"]
    ch_preds = (ch_probs >= THRESHOLD).astype(int)
    fp_count = int(ch_preds.sum())
    fpr      = fp_count / len(ch_texts)
    ch_fps[name]  = fp_count
    ch_fpr[name]  = fpr
    print(f"\n  [benign_challenge.csv (n={len(ch_texts)})]")
    print(f"    FP count : {fp_count}  FPR : {fpr:.1%}")

    # per-category
    cat_cnt  = Counter(ch_cats)
    cat_fp   = Counter()
    for pred, cat in zip(ch_preds, ch_cats):
        if pred:
            cat_fp[cat] += 1
    ch_cat_fp[name] = cat_fp
    print(f"    Per-category FP:")
    for cat in sorted(cat_cnt):
        n  = cat_cnt[cat]
        fp = cat_fp[cat]
        print(f"      {cat:<35} {fp:>4}/{n:<4} ({fp/n:.0%})")

# ── STEP 6: Known-failure prompt scores ─────────────────────────────────────
banner("STEP 6 - Known-Failure Prompt Scores")

col_w = max(len(p) for p in KNOWN_FAILURES) + 4
header = f"  {'Prompt':<{col_w}}"
for name, _ in active:
    header += f"  {name:<22}"
print(header)
hline()

for i, prompt in enumerate(KNOWN_FAILURES):
    row = f"  {repr(prompt):<{col_w}}"
    for name, _ in active:
        score = results[name]["kf_probs"][i]
        v = verdict(score)
        row += f"  {score:.4f} ({v:<9})"
    print(row)

# ── STEP 7: 3-way comparison table ──────────────────────────────────────────
banner("STEP 7 - Original vs Phase 5B vs Phase 5D Comparison")

names = [n for n, _ in active]

def row(label, vals, fmt=None):
    r = f"  {label:<38}"
    for v in vals:
        if fmt:
            r += f"  {fmt.format(v):>18}"
        else:
            r += f"  {str(v):>18}"
    return r

print(f"\n  {'Metric':<38}" + "".join(f"  {n:>18}" for n in names))
hline()

# test.csv metrics
print(f"  {'--- test.csv ---'}")
for metric, key, fmt in [
    ("Accuracy",  "acc",  "{:.4f}"),
    ("Precision", "prec", "{:.4f}"),
    ("Recall",    "rec",  "{:.4f}"),
    ("F1",        "f1",   "{:.4f}"),
    ("FP",        "fp",   "{:,}"),
    ("FN",        "fn",   "{:,}"),
    ("ROC-AUC",   "roc",  "{:.4f}"),
    ("PR-AUC",    "pr",   "{:.4f}"),
]:
    vals = [test_metrics[n][key] for n in names]
    print(row(metric, vals, fmt))

hline()

# zero-day
print(f"  {'--- zero-day (n=5000, fixed seed) ---'}")
for metric, key, fmt in [
    ("Attacks detected",  "detected", "{:,}"),
    ("Attacks missed",    "missed",   "{:,}"),
    ("Attack recall",     "recall",   "{:.4f}"),
]:
    vals = [zd_metrics[n][key] for n in names]
    print(row(metric, vals, fmt))

hline()

# challenge
print(f"  {'--- benign_challenge.csv (n=333) ---'}")
vals_fp  = [ch_fps[n]  for n in names]
vals_fpr = [ch_fpr[n]  for n in names]
print(row("False positives",    vals_fp,  "{:,}"))
print(row("False-positive rate", [f"{v:.1%}" for v in vals_fpr]))

# Delta vs original
if "Original" in names and len(names) > 1:
    orig_fp = ch_fps["Original"]
    print()
    for name in names:
        if name == "Original":
            continue
        delta   = ch_fps[name] - orig_fp
        delta_p = delta / max(orig_fp, 1) * 100
        sign    = "+" if delta > 0 else ""
        print(f"  {name} vs Original: FP {sign}{delta} ({sign}{delta_p:.1f}%)")

hline()

# Per-category challenge
print(f"  {'--- per-category FPR (benign_challenge.csv) ---'}")
cat_cnt = Counter(ch_cats)
print(f"  {'Category':<35}" + "".join(f"  {n:>18}" for n in names))
for cat in sorted(cat_cnt):
    n = cat_cnt[cat]
    vals = []
    for name in names:
        fp = ch_cat_fp[name][cat]
        vals.append(f"{fp}/{n} ({fp/n:.0%})")
    r = f"  {cat:<35}"
    for v in vals:
        r += f"  {v:>18}"
    print(r)

hline()

# ── STEP 8: Recommendation ──────────────────────────────────────────────────
banner("STEP 8 - Recommendation")

if "Phase 5D" in test_metrics and "Original" in test_metrics:
    orig_f1   = test_metrics["Original"]["f1"]
    p5d_f1    = test_metrics["Phase 5D"]["f1"]
    orig_zd   = zd_metrics["Original"]["recall"]
    p5d_zd    = zd_metrics["Phase 5D"]["recall"]
    orig_fp   = ch_fps["Original"]
    p5d_fp    = ch_fps["Phase 5D"]

    f1_delta  = p5d_f1  - orig_f1
    zd_delta  = p5d_zd  - orig_zd
    fp_delta  = orig_fp - p5d_fp   # positive = improvement
    fp_delta_pct = fp_delta / max(orig_fp, 1) * 100

    print(f"\n  Phase 5D vs Original:")
    print(f"    test.csv F1 delta      : {f1_delta:+.4f} ({'OK' if f1_delta >= -0.01 else 'DEGRADED'})")
    print(f"    Zero-day recall delta  : {zd_delta:+.4f} ({'OK' if zd_delta >= -0.01 else 'DEGRADED'})")
    print(f"    FP reduction           : {fp_delta:+d} ({fp_delta_pct:+.1f}%)")
    print()

    substantial = fp_delta_pct >= 30
    f1_ok       = f1_delta >= -0.01
    zd_ok       = zd_delta >= -0.01

    if substantial and f1_ok and zd_ok:
        verdict_str = ("APPROVE Phase 5D -- substantial FP reduction with "
                       "preserved test and zero-day performance.")
    elif substantial and not f1_ok:
        verdict_str = ("REVIEW -- FP reduction achieved but test F1 degraded "
                       "beyond 1%. Inspect per-class metrics before promoting.")
    elif not substantial:
        verdict_str = ("INSUFFICIENT -- FP reduction is below 30%. "
                       "Consider further dataset expansion or FusionEngine tuning.")
    else:
        verdict_str = "REVIEW -- Mixed results. Manual inspection required."

    print(f"  VERDICT: {verdict_str}")

print()
print("  NOTE: ml/final_model/ was NOT modified.")
print(f"  Phase 5D candidate is at: {MODEL_5D_OUT}")
print()
banner("Phase 5D Training + Evaluation Complete -- Awaiting Review")
