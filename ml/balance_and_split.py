"""
balance_and_split.py
Fixes class imbalance and creates the final train/val/test splits,
including a zero-day holdout set of never-seen-during-training attacks.

Run this AFTER merge_data.py has produced ../data/merged_dataset.csv
"""

import pandas as pd
from sklearn.model_selection import train_test_split
from datasets import load_dataset

RANDOM_SEED = 42
ZERO_DAY_LEVEL = "lakera_level_Level 8"  # held out entirely - our "unseen attack" test
TARGET_BENIGN_COUNT = 15000  # how many benign examples we want in total


def load_extra_benign(n_needed):
    """Pull clean instruction prompts from Alpaca to pad out the benign class."""
    print(f"\nFetching {n_needed} extra benign examples from tatsu-lab/alpaca...")
    ds = load_dataset("tatsu-lab/alpaca")
    df = pd.DataFrame(ds["train"])
    df["text"] = df["instruction"].fillna("") + " " + df["input"].fillna("")
    df["text"] = df["text"].str.strip()
    df = df[df["text"].str.len() > 0].drop_duplicates(subset="text")
    df = df.sample(n=min(n_needed, len(df)), random_state=RANDOM_SEED)
    df["label"] = 0
    df["source"] = "alpaca_benign"
    return df[["text", "label", "source"]]


if __name__ == "__main__":
    df = pd.read_csv("../data/merged_dataset.csv")
    print(f"Loaded {len(df)} rows")

    current_benign = (df["label"] == 0).sum()
    if current_benign < TARGET_BENIGN_COUNT:
        extra_benign = load_extra_benign(TARGET_BENIGN_COUNT - current_benign)
        df = pd.concat([df, extra_benign], ignore_index=True)
        print(f"Added {len(extra_benign)} benign examples. New total: {len(df)} rows")

    # ---- 1. Show label balance PER SOURCE first ----
    print("\nLabel balance by source:")
    print(df.groupby(["source", "label"]).size())

    # ---- 2. Split off the zero-day holdout BEFORE any balancing ----
    zero_day_df = df[df["source"] == ZERO_DAY_LEVEL].copy()
    remaining_df = df[df["source"] != ZERO_DAY_LEVEL].copy()
    print(f"\nZero-day holdout ({ZERO_DAY_LEVEL}): {len(zero_day_df)} rows (excluded from training entirely)")

    # ---- 3. Downsample remaining Lakera levels so they don't dominate ----
    lakera_mask = remaining_df["source"].str.startswith("lakera_level")
    lakera_df = remaining_df[lakera_mask]
    non_lakera_df = remaining_df[~lakera_mask]

    benign_count = (non_lakera_df["label"] == 0).sum()
    non_lakera_malicious_count = (non_lakera_df["label"] == 1).sum()
    print(f"\nBenign examples available: {benign_count}")
    print(f"Non-Lakera malicious examples already present (spml/deepset): {non_lakera_malicious_count}")

    # Target: total malicious (non-lakera malicious + sampled lakera) should be
    # roughly 1.5x benign count, so the final pool isn't dominated either way.
    target_total_malicious = int(benign_count * 1.5)
    target_lakera_total = max(0, min(len(lakera_df), target_total_malicious - non_lakera_malicious_count))
    lakera_sampled = (
        lakera_df.groupby("source", group_keys=False)
        .apply(lambda g: g.sample(
            n=min(len(g), max(1, target_lakera_total // lakera_df["source"].nunique())),
            random_state=RANDOM_SEED
        ))
    )
    print(f"Downsampled Lakera (excl. zero-day level): {len(lakera_df)} -> {len(lakera_sampled)}")

    balanced_df = pd.concat([non_lakera_df, lakera_sampled], ignore_index=True)
    print(f"\nBalanced training pool: {len(balanced_df)} rows")
    print(balanced_df["label"].value_counts())

    # ---- 4. Train / val / test split (stratified by label) ----
    train_df, temp_df = train_test_split(
        balanced_df, test_size=0.3, stratify=balanced_df["label"], random_state=RANDOM_SEED
    )
    val_df, test_df = train_test_split(
        temp_df, test_size=0.5, stratify=temp_df["label"], random_state=RANDOM_SEED
    )

    print(f"\nTrain: {len(train_df)} | Val: {len(val_df)} | Test: {len(test_df)} | Zero-day: {len(zero_day_df)}")

    train_df.to_csv("../data/train.csv", index=False)
    val_df.to_csv("../data/val.csv", index=False)
    test_df.to_csv("../data/test.csv", index=False)
    zero_day_df.to_csv("../data/zero_day_test.csv", index=False)

    print("\nSaved: train.csv, val.csv, test.csv, zero_day_test.csv in ../data/")