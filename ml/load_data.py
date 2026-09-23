"""
load_data.py
Loads and merges prompt injection datasets for training.
Datasets:
  - deepset/prompt-injections
  - reshabhs/SPML_Chatbot_Prompt_Injection
  - Lakera/mosscap_prompt_injection

Output: a single cleaned pandas DataFrame with columns ["text", "label"]
where label = 1 (malicious / injection) or 0 (benign).
"""

from datasets import load_dataset
import pandas as pd


def load_deepset():
    ds = load_dataset("deepset/prompt-injections")
    df = pd.DataFrame(ds["train"])
    print("deepset columns:", df.columns.tolist())
    print(df.head(2))
    return df


def load_spml():
    ds = load_dataset("reshabhs/SPML_Chatbot_Prompt_Injection")
    split = "train" if "train" in ds else list(ds.keys())[0]
    df = pd.DataFrame(ds[split])
    print("SPML columns:", df.columns.tolist())
    print(df.head(2))
    return df


def load_lakera():
    ds = load_dataset("Lakera/mosscap_prompt_injection")
    split = "train" if "train" in ds else list(ds.keys())[0]
    df = pd.DataFrame(ds[split])
    print("Lakera columns:", df.columns.tolist())
    print(df.head(2))
    return df


if __name__ == "__main__":
    print("=== Loading deepset/prompt-injections ===")
    df_deepset = load_deepset()

    print("\n=== Loading reshabhs/SPML_Chatbot_Prompt_Injection ===")
    df_spml = load_spml()

    print("\n=== Loading Lakera/mosscap_prompt_injection ===")
    df_lakera = load_lakera()

    print("\nAll three datasets loaded. Inspect the printed column names above")
    print("before we write the merge/normalization step.")