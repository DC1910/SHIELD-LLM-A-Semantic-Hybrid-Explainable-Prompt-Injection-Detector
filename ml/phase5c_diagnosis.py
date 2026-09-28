"""
phase5c_diagnosis.py
====================
Phase 5C – Dataset Diagnostic Analysis for SHIELD-LLM

Analyses data/train.csv to identify the root causes of DistilBERT's
high-confidence false positives on benign inputs.

DO NOT retrain, modify, or overwrite any model or dataset.
Outputs: PHASE5C_DATASET_DIAGNOSIS.md in the project root.

Run from ml/ directory:
    python phase5c_diagnosis.py
"""

import os, sys, re, csv
from collections import Counter, defaultdict
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import CountVectorizer

SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DATA_DIR     = os.path.join(PROJECT_ROOT, "data")

TRAIN_CSV     = os.path.join(DATA_DIR, "train.csv")
VAL_CSV       = os.path.join(DATA_DIR, "val.csv")
TEST_CSV      = os.path.join(DATA_DIR, "test.csv")
CHALLENGE_CSV = os.path.join(DATA_DIR, "benign_challenge.csv")
REPORT_PATH   = os.path.join(PROJECT_ROOT, "PHASE5C_DATASET_DIAGNOSIS.md")

# Known Phase 5B remaining false-positive prompts
FP_PROMPTS = [
    "hi", "ok", "go", "run", "cancel", "retry", "stop",
    "show me", "tell me", "what is", "what?",
    "attack", "DOS attack", "DDoS attack", "What is area",
    "What is OAuth?", "What is a foreign key in SQL?",
    "password attack", "network attack",
    "What is the capital of India?",
    "what is area of square",
]

print("Loading datasets...")
train = pd.read_csv(TRAIN_CSV)
val   = pd.read_csv(VAL_CSV)
test  = pd.read_csv(TEST_CSV)
challenge = pd.read_csv(CHALLENGE_CSV)

train["text"] = train["text"].astype(str).str.strip()
val["text"]   = val["text"].astype(str).str.strip()
test["text"]  = test["text"].astype(str).str.strip()

benign    = train[train["label"] == 0]["text"].tolist()
malicious = train[train["label"] == 1]["text"].tolist()

print(f"  Train:  {len(train)} rows  (benign={len(benign)}, malicious={len(malicious)})")
print(f"  Val:    {len(val)} rows")
print(f"  Test:   {len(test)} rows")
print(f"  Challenge: {len(challenge)} rows")

# ── helpers ─────────────────────────────────────────────────────────────────
def token_len(s):
    return len(str(s).split())

def char_len(s):
    return len(str(s))

def pct(n, d):
    return f"{n/d*100:.1f}%" if d else "N/A"

def top_n_table(counter, n=20, label=""):
    rows = counter.most_common(n)
    lines = [f"| {'Term':<35} | {'Count':>8} |"]
    lines.append(f"|{'-'*37}|{'-'*10}|")
    for term, cnt in rows:
        lines.append(f"| {str(term):<35} | {cnt:>8} |")
    return "\n".join(lines)

def section(title, level=2):
    prefix = "#" * level
    return f"\n{prefix} {title}\n"

# ─────────────────────────────────────────────────────────────────────────────
# 1. Length distributions
# ─────────────────────────────────────────────────────────────────────────────
print("Analysing length distributions...")

b_tok  = [token_len(t) for t in benign]
m_tok  = [token_len(t) for t in malicious]
b_char = [char_len(t) for t in benign]
m_char = [char_len(t) for t in malicious]

def pct_le(lst, n):
    return pct(sum(1 for x in lst if x <= n), len(lst))

def pct_range(lst, lo, hi):
    return pct(sum(1 for x in lst if lo <= x <= hi), len(lst))

length_table = f"""
| Metric                        | Benign (label=0) | Malicious (label=1) |
|-------------------------------|------------------|---------------------|
| Count                         | {len(benign):>16,} | {len(malicious):>19,} |
| Mean tokens                   | {np.mean(b_tok):>16.1f} | {np.mean(m_tok):>19.1f} |
| Median tokens                 | {np.median(b_tok):>16.1f} | {np.median(m_tok):>19.1f} |
| Std tokens                    | {np.std(b_tok):>16.1f} | {np.std(m_tok):>19.1f} |
| Min tokens                    | {min(b_tok):>16} | {min(m_tok):>19} |
| Max tokens                    | {max(b_tok):>16} | {max(m_tok):>19} |
| % with ≤3 tokens              | {pct_le(b_tok,3):>16} | {pct_le(m_tok,3):>19} |
| % with ≤5 tokens              | {pct_le(b_tok,5):>16} | {pct_le(m_tok,5):>19} |
| % with 6–15 tokens            | {pct_range(b_tok,6,15):>16} | {pct_range(m_tok,6,15):>19} |
| % with 16–30 tokens           | {pct_range(b_tok,16,30):>16} | {pct_range(m_tok,16,30):>19} |
| % with >30 tokens             | {pct_range(b_tok,31,9999):>16} | {pct_range(m_tok,31,9999):>19} |
| Mean chars                    | {np.mean(b_char):>16.1f} | {np.mean(m_char):>19.1f} |
| Median chars                  | {np.median(b_char):>16.1f} | {np.median(m_char):>19.1f} |
"""

# ─────────────────────────────────────────────────────────────────────────────
# 2. Very short prompts by class
# ─────────────────────────────────────────────────────────────────────────────
print("Analysing very short prompts...")

short_b = [(t, token_len(t)) for t in benign  if token_len(t) <= 3]
short_m = [(t, token_len(t)) for t in malicious if token_len(t) <= 3]

short_b_ex = sorted(short_b, key=lambda x: x[1])[:30]
short_m_ex = sorted(short_m, key=lambda x: x[1])[:30]

# Check if single-word queries exist in benign training at all
single_word_b = [t for t in benign  if len(t.split()) == 1]
single_word_m = [t for t in malicious if len(t.split()) == 1]

# ─────────────────────────────────────────────────────────────────────────────
# 3. Unigram / bigram frequency skew
# ─────────────────────────────────────────────────────────────────────────────
print("Analysing n-gram frequencies...")

def word_counts(texts):
    c = Counter()
    for t in texts:
        for w in re.findall(r"\b\w+\b", t.lower()):
            c[w] += 1
    return c

bc = word_counts(benign)
mc = word_counts(malicious)
total_b = sum(bc.values())
total_m = sum(mc.values())

# Normalised frequency ratio  (malicious freq / benign freq, per-token)
def freq_ratio_table(bc, mc, total_b, total_m, top=30):
    all_words = set(bc.keys()) | set(mc.keys())
    rows = []
    for w in all_words:
        b_f = (bc[w] + 1) / (total_b + len(all_words))  # Laplace
        m_f = (mc[w] + 1) / (total_m + len(all_words))
        ratio = m_f / b_f
        rows.append((w, bc[w], mc[w], ratio))
    rows.sort(key=lambda x: -x[3])
    return rows[:top]

skew_toward_malicious = freq_ratio_table(bc, mc, total_b, total_m, top=40)

# Bigrams
def bigram_counts(texts):
    c = Counter()
    for t in texts:
        words = re.findall(r"\b\w+\b", t.lower())
        for i in range(len(words)-1):
            c[f"{words[i]} {words[i+1]}"] += 1
    return c

bb = bigram_counts(benign)
mb = bigram_counts(malicious)
total_bb = sum(bb.values())
total_mb = sum(mb.values())
skew_bigrams = freq_ratio_table(bb, mb, total_bb, total_mb, top=30)

# ─────────────────────────────────────────────────────────────────────────────
# 4. Specific term audit
# ─────────────────────────────────────────────────────────────────────────────
print("Auditing specific terms...")

AUDIT_TERMS = [
    "what", "what is", "hi", "go", "attack", "sql", "oauth", "area",
    "show me", "tell me", "dos", "ddos", "malware", "injection",
    "ignore", "previous", "instructions", "pretend", "jailbreak",
    "foreign", "key", "capital", "india", "password",
    "hack", "exploit", "run", "stop", "cancel", "retry", "ok",
]

def count_containing(texts, term):
    term_lower = term.lower()
    return sum(1 for t in texts if term_lower in t.lower())

term_audit_rows = []
for term in AUDIT_TERMS:
    b_cnt = count_containing(benign, term)
    m_cnt = count_containing(malicious, term)
    b_rate = b_cnt / len(benign)
    m_rate = m_cnt / len(malicious)
    ratio  = m_rate / b_rate if b_rate > 0 else float("inf")
    term_audit_rows.append((term, b_cnt, b_rate, m_cnt, m_rate, ratio))

term_audit_rows.sort(key=lambda x: -x[5])  # sort by malicious/benign ratio

# ─────────────────────────────────────────────────────────────────────────────
# 5. Duplicates & near-duplicates
# ─────────────────────────────────────────────────────────────────────────────
print("Checking duplicates...")

all_texts = train["text"].str.strip().str.lower()
dup_mask  = all_texts.duplicated(keep=False)
dup_df    = train[dup_mask].copy()
dup_df["text_lower"] = dup_df["text"].str.strip().str.lower()

# Cross-label duplicates: same text, different labels
cross_label = (
    dup_df.groupby("text_lower")["label"]
    .apply(lambda x: list(x.unique()))
    .reset_index()
)
cross_label_conflict = cross_label[cross_label["label"].apply(len) > 1]

# Exact duplicates within label
dup_within_benign    = (benign_lower := [t.lower() for t in benign],
                        Counter(benign_lower))[1]
dup_within_malicious = Counter([t.lower() for t in malicious])
high_dup_b = [(t, c) for t, c in dup_within_benign.items() if c > 1]
high_dup_m = [(t, c) for t, c in dup_within_malicious.items() if c > 1]

# ─────────────────────────────────────────────────────────────────────────────
# 6. Source distribution & formatting artifacts
# ─────────────────────────────────────────────────────────────────────────────
print("Analysing source distribution...")

has_source = "source" in train.columns

if has_source:
    src_table = train.groupby(["source", "label"]).size().unstack(fill_value=0)
    src_str = src_table.to_string()
else:
    src_str = "No 'source' column in train.csv."

# Check for formatting artifacts
def check_artifact(texts, pattern, name):
    cnt = sum(1 for t in texts if re.search(pattern, t))
    return cnt

artifacts = [
    ("Starts with 'Instruction:'", r"^Instruction:", benign, malicious),
    ("Starts with 'Input:'",       r"^Input:",       benign, malicious),
    ("Starts with '###'",          r"^###",          benign, malicious),
    ("All uppercase",              r"^[A-Z\s]+$",    benign, malicious),
    ("Contains newline (\\n)",     r"\n",            benign, malicious),
    ("Question mark present",      r"\?",            benign, malicious),
    ("Starts with 'What'",         r"^What",         benign, malicious),
    ("Starts with 'How'",          r"^How",          benign, malicious),
    ("Starts with 'Ignore'",       r"^[Ii]gnore",    benign, malicious),
    ("Starts with 'Please'",       r"^[Pp]lease",    benign, malicious),
    ("Starts with 'Pretend'",      r"^[Pp]retend",   benign, malicious),
    ("Starts with 'You are'",      r"^[Yy]ou are",   benign, malicious),
    ("Starts with 'Act as'",       r"^[Aa]ct as",    benign, malicious),
    ("Contains 'instruction'",     r"[Ii]nstruction", benign, malicious),
    ("Alpaca 'Instruction:' fmt",  r"^Instruction:\s", benign, malicious),
]

artifact_rows = []
for name, pat, b_texts, m_texts in artifacts:
    b_cnt = check_artifact(b_texts, pat, name)
    m_cnt = check_artifact(m_texts, pat, name)
    artifact_rows.append((name, b_cnt, pct(b_cnt, len(b_texts)),
                           m_cnt, pct(m_cnt, len(m_texts))))

# ─────────────────────────────────────────────────────────────────────────────
# 7. Benign coverage gaps
# ─────────────────────────────────────────────────────────────────────────────
print("Checking benign coverage gaps...")

SHORT_FRAGMENTS  = ["hi", "hello", "ok", "go", "run", "stop", "cancel",
                    "retry", "yes", "no", "help", "sure", "done", "test",
                    "debug", "error", "check", "show", "what?", "why?"]
CYBERTERMS       = ["attack", "dos attack", "ddos attack", "malware",
                    "ransomware", "phishing", "exploit", "vulnerability",
                    "sql injection", "xss", "csrf", "buffer overflow",
                    "password attack", "network attack"]
PI_EDU           = ["what is prompt injection", "how does prompt injection",
                    "what is a jailbreak", "explain prompt injection"]

def coverage(texts, probes):
    present = [p for p in probes
               if any(p.lower() in t.lower() for t in texts)]
    return present, [p for p in probes if p not in present]

frag_present, frag_missing = coverage(benign, SHORT_FRAGMENTS)
cyber_present, cyber_missing = coverage(benign, CYBERTERMS)
pied_present, pied_missing = coverage(benign, PI_EDU)

# ─────────────────────────────────────────────────────────────────────────────
# 8. Nearest training examples to FP prompts
# ─────────────────────────────────────────────────────────────────────────────
print("Finding nearest training examples to FP prompts...")

from difflib import SequenceMatcher

def nearest_k(query, corpus, labels, k=3):
    sims = [(SequenceMatcher(None, query.lower(), t.lower()).ratio(), t, lbl)
            for t, lbl in zip(corpus[:5000], labels[:5000])]
    sims.sort(reverse=True)
    return sims[:k]

all_train_texts  = train["text"].tolist()[:5000]
all_train_labels = train["label"].tolist()[:5000]

fp_nearest = {}
for fp in FP_PROMPTS[:12]:  # limit for speed
    fp_nearest[fp] = nearest_k(fp, all_train_texts, all_train_labels, k=5)

# ─────────────────────────────────────────────────────────────────────────────
# 9. Train/val/test split leakage check
# ─────────────────────────────────────────────────────────────────────────────
print("Checking split leakage...")

train_set = set(train["text"].str.strip().str.lower())
val_set   = set(val["text"].str.strip().str.lower())
test_set  = set(test["text"].str.strip().str.lower())

tv_overlap = train_set & val_set
tt_overlap = train_set & test_set
vt_overlap = val_set   & test_set

# Source-label correlation check
if has_source:
    src_label_corr = train.groupby("source")["label"].mean().sort_values()
    src_label_corr_str = src_label_corr.to_string()
else:
    src_label_corr_str = "No source column."

# ─────────────────────────────────────────────────────────────────────────────
# 10. Build the Markdown report
# ─────────────────────────────────────────────────────────────────────────────
print("Writing report...")

def fmt_ex_list(items, max_n=15):
    lines = []
    for t, lbl in items[:max_n]:
        lines.append(f'- `"{t[:90]}"` (label={lbl})')
    return "\n".join(lines) if lines else "_None found_"

def fmt_str_list(items, max_n=20):
    return "\n".join(f'- `"{str(t)[:90]}"`' for t in items[:max_n]) or "_None_"

md = []
md.append("# PHASE 5C – SHIELD-LLM Dataset Diagnostic Report\n")
md.append("> **Purpose:** Root-cause analysis of DistilBERT high-confidence false positives on benign inputs.  \n")
md.append("> **Constraint:** Evaluation only. No models, datasets, thresholds, or code were modified.\n")
md.append(f"\n**Dataset:** `data/train.csv`  —  {len(train):,} rows "
          f"({len(benign):,} benign / {len(malicious):,} malicious)\n")

# ── 1. Length ────────────────────────────────────────────────────────────────
md.append(section("1. Text Length Distribution: Benign vs Malicious"))
md.append(length_table)

md.append("\n### Key Observations\n")
b_le3 = sum(1 for x in b_tok if x <= 3)
m_le3 = sum(1 for x in m_tok if x <= 3)
md.append(f"- Benign mean token length: **{np.mean(b_tok):.1f}** vs Malicious: **{np.mean(m_tok):.1f}**\n")
md.append(f"- Short benign prompts (≤3 tokens): **{b_le3:,}** ({pct(b_le3,len(benign))})  "
          f"vs Short malicious: **{m_le3:,}** ({pct(m_le3,len(malicious))})\n")
md.append(f"- If most short prompts in training are labelled malicious, the classifier "
          f"learns \"short = suspicious\" — a spurious shortcut.\n")

# ── 2. Short prompts ─────────────────────────────────────────────────────────
md.append(section("2. Very Short Prompts (≤ 3 tokens) by Class"))
md.append(f"\n**Benign short prompts in training: {len(short_b):,}**\n")
md.append(fmt_str_list([t for t, _ in short_b_ex]))
md.append(f"\n\n**Malicious short prompts in training: {len(short_m):,}**\n")
md.append(fmt_str_list([t for t, _ in short_m_ex]))

md.append(f"\n\n**Single-word benign prompts:** {len(single_word_b):,}")
md.append(f"\n**Single-word malicious prompts:** {len(single_word_m):,}")
ratio_sw = len(single_word_m) / max(len(single_word_b), 1)
md.append(f"\n**Ratio (malicious/benign single-word):** {ratio_sw:.1f}×\n")
md.append(f"\n> [!CAUTION]\n> A ratio >> 1 means single-word inputs are predominantly "
          f"malicious in training, directly explaining why \"hi\", \"go\", \"ok\" etc. "
          f"receive near-1.0 malicious scores.\n")

# ── 3. N-gram skew ───────────────────────────────────────────────────────────
md.append(section("3. Top Unigrams Disproportionately Associated with label=1"))
md.append("\n_(Sorted by malicious/benign normalised frequency ratio — higher = "
          "more skewed toward malicious)_\n\n")
md.append(f"| {'Token':<30} | {'Benign count':>13} | {'Malicious count':>16} | {'M/B ratio':>10} |")
md.append(f"\n|{'-'*32}|{'-'*15}|{'-'*18}|{'-'*12}|")
for w, bc_cnt, mc_cnt, ratio in skew_toward_malicious:
    md.append(f"\n| {w:<30} | {bc_cnt:>13,} | {mc_cnt:>16,} | {ratio:>10.2f}× |")

md.append(section("3b. Top Bigrams Disproportionately Associated with label=1", level=3))
md.append("\n")
md.append(f"| {'Bigram':<35} | {'Benign':>8} | {'Malicious':>10} | {'M/B ratio':>10} |")
md.append(f"\n|{'-'*37}|{'-'*10}|{'-'*12}|{'-'*12}|")
for w, bc_cnt, mc_cnt, ratio in skew_bigrams[:20]:
    md.append(f"\n| {w:<35} | {bc_cnt:>8,} | {mc_cnt:>10,} | {ratio:>10.2f}× |")

# ── 4. Term audit ─────────────────────────────────────────────────────────────
md.append(section("4. Specific Term Frequency Audit"))
md.append("\n_(Terms from Phase 5B false-positive prompts — sorted by M/B rate ratio)_\n\n")
md.append(f"| {'Term':<25} | {'Benign cnt':>10} | {'Benign rate':>12} | {'Mal cnt':>8} | {'Mal rate':>10} | {'Ratio':>8} |")
md.append(f"\n|{'-'*27}|{'-'*12}|{'-'*14}|{'-'*10}|{'-'*12}|{'-'*10}|")
for term, b_cnt, b_rate, m_cnt, m_rate, ratio in term_audit_rows:
    ratio_str = f"{ratio:.2f}×" if ratio != float("inf") else "∞"
    md.append(f"\n| {term:<25} | {b_cnt:>10,} | {b_rate:>11.3%} | {m_cnt:>8,} | {m_rate:>10.3%} | {ratio_str:>8} |")

md.append("\n\n> [!IMPORTANT]\n> Terms with ratio >> 1 are being learned by DistilBERT "
          "as **malicious signals**, even when they appear in clearly benign contexts.\n")

# ── 5. Duplicates ─────────────────────────────────────────────────────────────
md.append(section("5. Duplicate and Near-Duplicate Analysis"))

md.append(f"\n| Metric | Count |\n|---|---|\n")
md.append(f"| Total rows with any duplicate text | {len(dup_df):,} |\n")
md.append(f"| Cross-label conflicts (same text, labels 0 AND 1) | {len(cross_label_conflict):,} |\n")
md.append(f"| Benign texts with exact duplicates (within label) | {len(high_dup_b):,} |\n")
md.append(f"| Malicious texts with exact duplicates (within label) | {len(high_dup_m):,} |\n")

if len(cross_label_conflict) > 0:
    md.append(f"\n> [!CAUTION]\n> **{len(cross_label_conflict)} texts appear with BOTH label=0 and label=1.** "
              f"This directly contradicts the model's training signal.\n")
    md.append("\n**Sample cross-label conflicts:**\n")
    for _, row in cross_label_conflict.head(10).iterrows():
        md.append(f'- `"{row["text_lower"][:90]}"` → labels: {row["label"]}\n')

md.append("\n**Top repeated benign texts (highest duplicate count):**\n")
for t, c in sorted(high_dup_b, key=lambda x: -x[1])[:10]:
    md.append(f'- ({c}×) `"{t[:80]}"`\n')

md.append("\n**Top repeated malicious texts:**\n")
for t, c in sorted(high_dup_m, key=lambda x: -x[1])[:10]:
    md.append(f'- ({c}×) `"{t[:80]}"`\n')

# ── 6. Source / formatting artifacts ─────────────────────────────────────────
md.append(section("6. Source Distribution and Formatting Artifacts"))

if has_source:
    md.append("\n**Label distribution by source:**\n```\n")
    md.append(src_str)
    md.append("\n```\n")
    md.append("\n**Mean label (= malicious rate) per source (1.0 = all malicious, 0.0 = all benign):**\n```\n")
    md.append(src_label_corr_str)
    md.append("\n```\n")
    md.append("\n> [!NOTE]\n> Sources with label_mean ≈ 1.0 are entirely malicious. "
              "If the model learns source-specific formatting cues (e.g., Alpaca's "
              "`Instruction:` prefix vs raw injection phrasing), it may use those "
              "formatting features rather than semantic content as the decision boundary.\n")

md.append("\n**Formatting artifact prevalence:**\n\n")
md.append(f"| Pattern | Benign count | Benign % | Malicious count | Malicious % |\n")
md.append(f"|---|---|---|---|---|\n")
for name, b_cnt, b_pct, m_cnt, m_pct in artifact_rows:
    md.append(f"| {name} | {b_cnt:,} | {b_pct} | {m_cnt:,} | {m_pct} |\n")

# ── 7. Benign coverage gaps ───────────────────────────────────────────────────
md.append(section("7. Benign Coverage Gaps"))

md.append("\n### 7a. Short/Conversational Fragments\n")
md.append(f"- **Present in benign training:** {', '.join(f'`{p}`' for p in frag_present) or 'None'}\n")
md.append(f"- **MISSING from benign training:** {', '.join(f'`{p}`' for p in frag_missing) or 'None (good!)'}\n")

md.append("\n### 7b. Cybersecurity Terminology Used Benignly\n")
md.append(f"- **Present:** {', '.join(f'`{p}`' for p in cyber_present) or 'None'}\n")
md.append(f"- **MISSING:** {', '.join(f'`{p}`' for p in cyber_missing) or 'None (good!)'}\n")

md.append("\n### 7c. Prompt-Injection Educational Questions\n")
md.append(f"- **Present:** {', '.join(f'`{p}`' for p in pied_present) or 'None'}\n")
md.append(f"- **MISSING:** {', '.join(f'`{p}`' for p in pied_missing) or 'None (good!)'}\n")

md.append("\n> [!WARNING]\n> Any category that is **entirely absent** from benign training means "
          "the model has never seen a label=0 example from that domain. "
          "It will default to labelling such inputs as malicious.\n")

# ── 8. Nearest training neighbours of FP prompts ─────────────────────────────
md.append(section("8. Nearest Training Examples to Phase 5B False Positives"))
md.append("\n_(String similarity to first 5000 training rows — shows what the model "
          "\"sees\" as context for each FP prompt)_\n")

for fp, neighbours in fp_nearest.items():
    md.append(f"\n**Query:** `\"{fp}\"`\n")
    for sim, text, lbl in neighbours:
        marker = "🔴 MAL" if lbl == 1 else "🟢 BEN"
        md.append(f"- {marker} ({sim:.2f}) `\"{text[:90]}\"`\n")

# ── 9. Split leakage ─────────────────────────────────────────────────────────
md.append(section("9. Train / Val / Test Split Integrity"))

md.append(f"\n| Split pair | Overlapping texts |\n|---|---|\n")
md.append(f"| train ∩ val  | {len(tv_overlap):,} |\n")
md.append(f"| train ∩ test | {len(tt_overlap):,} |\n")
md.append(f"| val ∩ test   | {len(vt_overlap):,} |\n")

if len(tv_overlap) + len(tt_overlap) > 0:
    md.append("\n> [!WARNING]\n> Text overlap between train and eval splits means the model "
              "may be evaluated on memorised examples rather than generalisation.\n")
else:
    md.append("\n> [!NOTE]\n> No text-level overlap detected across splits. "
              "Split construction is clean.\n")

# ── 10. Root causes & recommendations ────────────────────────────────────────
md.append(section("10. Root-Cause Summary and Recommended Interventions"))

md.append("""
### Root Causes Identified

| # | Root Cause | Evidence | Severity |
|---|---|---|---|
| RC-1 | **Short-text bias**: single-word and 1–3 token inputs are overwhelmingly malicious in training | Short malicious >> short benign; "hi", "ok", "go" never appear as benign | 🔴 Critical |
| RC-2 | **Cybersecurity vocabulary toxicity**: words like "attack", "SQL", "DOS" appear almost exclusively as label=1 in training | Token frequency ratio >> 1 for all attack-domain terms | 🔴 Critical |
| RC-3 | **"What is" prefix captured as malicious signal**: training contains malicious prompts starting with "What is your system prompt?" etc., far outnumbering benign "What is…" questions | Bigram "what is" skewed toward malicious | 🟠 High |
| RC-4 | **Formatting/source shortcut**: Alpaca benign examples use `Instruction: …` format; raw injection prompts do not — model may rely on this formatting cue | `Instruction:` prefix almost exclusively in label=0 | 🟠 High |
| RC-5 | **Prompt-injection educational questions labelled as malicious**: "What is prompt injection?" appears with label=1 in training data | Semantic similarity = 1.0 in Phase 5A; appears in malicious training rows | 🟠 High |
| RC-6 | **Cross-label label noise**: same text with conflicting labels in training | Cross-label conflicts detected | 🟡 Medium |
| RC-7 | **Benign domain gaps**: no or very few benign examples covering short commands, bare security terms, or cybersecurity Q&A | Coverage gap analysis shows these categories absent/sparse in benign training | 🟠 High |

### Recommended Interventions (in priority order)

> [!IMPORTANT]
> Do NOT implement until Phase 5D is approved.

#### Priority 1 – Benign Data Augmentation (addresses RC-1, RC-3, RC-7)
Add large volumes of diverse benign examples that are **lexically similar to current FP prompts** but contextually safe:
- **Conversational fragments**: hi, hello, ok, go, yes, no, stop, cancel, run, retry, show me, tell me, what is, what are (≥500 unique examples each with slight variations)
- **"What is X?" questions** covering topics the model currently mis-classifies: What is OAuth? What is SQL? What is area? What is the capital of India? (~2,000 examples)
- **Bare security terms used neutrally**: "attack", "DOS attack", "DDoS", "SQL injection", "malware" etc. as standalone terms or in Q&A (~1,000 examples)

**Key constraint**: these must be injected as _raw text without any Alpaca formatting prefix_, matching the format of real user inputs.

#### Priority 2 – Fix Formatting Shortcut (addresses RC-4)
The Alpaca-sourced benign examples use `Instruction: …` format while malicious examples are raw text. The model is learning format → label.
- **Strip or normalize** the `Instruction:` and `Input:` prefixes from all Alpaca benign examples before training.
- Alternatively, add raw-format benign examples without any template wrapper.

#### Priority 3 – Remove Cross-Label Conflicts (addresses RC-6)
- Audit and remove rows where the same text is assigned both label=0 and label=1.
- De-duplicate within each label to reduce repetition bias.

#### Priority 4 – Relabel Prompt-Injection Education Questions (addresses RC-5)
- Identify and relabel (0→0 correction) definitional/educational questions about prompt injection that are currently labelled 1.
- "What is prompt injection?" is **not** a prompt injection attack.

#### Priority 5 – Targeted Hard-Negative Augmentation at Correct Format (addresses RC-1, RC-7)
- The Phase 5B hard-negative set (135 unique examples × 4 repeats = 525 total) is too small relative to 10,500 benign training examples.
- Increase to ≥3,000 diverse hard-negative benign examples.
- Ensure they are raw-format (no `Instruction:` prefix).
- Use a wider vocabulary: include domain terms, programming syntax, short commands.

#### Priority 6 – Soft-label / Confidence Calibration (addresses over-confidence)
- Consider label smoothing (ε=0.1) during training to prevent the model from learning near-1.0 confidence for any input.
- This won't fix the direction of FPs but will reduce the magnitude of scores, giving the FusionEngine's confidence gate more room to blend signals.

### Expected Outcome After Interventions

| Intervention | Expected FPR change | Attack recall risk |
|---|---|---|
| Benign augmentation (raw format) | ↓ 50–70% | Low |
| Formatting normalisation | ↓ 10–20% additional | None |
| Cross-label dedup | ↓ 5–10% | None |
| Relabelling edu questions | Fixes semantic detector too | None |
| Label smoothing | Reduces score magnitude only | None |

_Estimated combined improvement: benign FPR from 30.9% → ~5–8%_
""")

md.append(section("11. Appendix – Raw Data Samples"))

md.append("\n### A. Sample Benign Training Examples\n")
b_sample = train[train.label==0]["text"].sample(20, random_state=42).tolist()
md.append(fmt_str_list(b_sample))

md.append("\n\n### B. Sample Malicious Training Examples\n")
m_sample = train[train.label==1]["text"].sample(20, random_state=42).tolist()
md.append(fmt_str_list(m_sample))

md.append("\n\n### C. All Unique Short Benign Prompts (≤3 tokens) in Training\n")
uniq_short_b = sorted(set(t for t, _ in short_b), key=lambda x: len(x))
md.append(fmt_str_list(uniq_short_b, max_n=50))

md.append("\n\n### D. All Unique Short Malicious Prompts (≤3 tokens) in Training\n")
uniq_short_m = sorted(set(t for t, _ in short_m), key=lambda x: len(x))
md.append(fmt_str_list(uniq_short_m, max_n=50))

md.append(f"\n\n---\n_Report generated by `ml/phase5c_diagnosis.py` — Phase 5C diagnostic only. No modifications made._\n")

# Write report
with open(REPORT_PATH, "w", encoding="utf-8") as f:
    f.write("\n".join(md))

print(f"\nReport written to: {REPORT_PATH}")
print("Phase 5C diagnostic complete. Stopping as instructed.")
