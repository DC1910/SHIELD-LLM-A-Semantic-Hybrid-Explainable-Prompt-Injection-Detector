"""
merge_data.py
Normalizes and merges the three datasets into a single schema:
    text  -> the prompt/content to classify
    label -> 1 = malicious/injection, 0 = benign
    source -> which dataset the row came from (useful for later analysis)

Run this AFTER load_data.py has confirmed the schemas.
Outputs: ../data/merged_dataset.csv
"""

from datasets import load_dataset
import pandas as pd
import os


def build_deepset():
    ds = load_dataset("deepset/prompt-injections")
    df = pd.concat([pd.DataFrame(ds["train"]), pd.DataFrame(ds["test"])], ignore_index=True)
    df = df.rename(columns={"text": "text", "label": "label"})
    df = df[["text", "label"]]
    df["source"] = "deepset"
    return df


def build_spml():
    ds = load_dataset("reshabhs/SPML_Chatbot_Prompt_Injection")
    df = pd.DataFrame(ds["train"])

    # Combine system + user prompt into one text field -
    # the injection attempt usually lives in the user prompt,
    # but system prompt gives context that can matter for detection.
    df["text"] = (
        "System: " + df["System Prompt"].fillna("") +
        "\nUser: " + df["User Prompt"].fillna("")
    )

    # Normalize label column to 0/1 ints
    df["label"] = pd.to_numeric(df["Prompt injection"], errors="coerce").fillna(0).astype(int)
    df["label"] = df["label"].clip(0, 1)  # safety in case of stray values

    df["source"] = "spml"
    return df[["text", "label", "source"]]


def build_lakera():
    ds = load_dataset("Lakera/mosscap_prompt_injection")
    df = pd.concat(
        [pd.DataFrame(ds["train"]), pd.DataFrame(ds["validation"]), pd.DataFrame(ds["test"])],
        ignore_index=True,
    )
    df["text"] = df["prompt"]
    # Every row in this dataset IS a prompt injection attempt (game/red-team data)
    df["label"] = 1
    df["source"] = "lakera_level_" + df["level"].astype(str)
    return df[["text", "label", "source"]]


if __name__ == "__main__":
    print("Building deepset...")
    df1 = build_deepset()
    print(f"  -> {len(df1)} rows")

    print("Building SPML...")
    df2 = build_spml()
    print(f"  -> {len(df2)} rows")

    print("Building Lakera...")
    df3 = build_lakera()
    print(f"  -> {len(df3)} rows")

    merged = pd.concat([df1, df2, df3], ignore_index=True)

    # Drop empty/duplicate text rows
    merged["text"] = merged["text"].astype(str).str.strip()
    merged = merged[merged["text"].str.len() > 0]
    before = len(merged)
    merged = merged.drop_duplicates(subset="text")
    print(f"\nDropped {before - len(merged)} duplicate rows")

    print(f"\nFinal merged dataset: {len(merged)} rows")
    print(merged["label"].value_counts())
    print("\nSource breakdown:")
    print(merged["source"].value_counts())

    os.makedirs("../data", exist_ok=True)
    merged.to_csv("../data/merged_dataset.csv", index=False)
    print("\nSaved to ../data/merged_dataset.csv")