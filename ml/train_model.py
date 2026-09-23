"""
train_model.py
Fine-tunes DistilBERT for binary prompt injection classification.
Tuned for a 4GB VRAM GPU (GTX 1650): small batch size, capped sequence length,
gradient accumulation to simulate a larger effective batch size.

Supports pause/resume via checkpoints saved every epoch.

Run:
    python train_model.py                       # fresh run
    python train_model.py --resume               # resume from last checkpoint
"""

import argparse
import numpy as np
import pandas as pd
import torch
from datasets import Dataset
from sklearn.metrics import accuracy_score, precision_recall_fscore_support
from transformers import (
    AutoTokenizer,
    AutoModelForSequenceClassification,
    TrainingArguments,
    Trainer,
)

MODEL_NAME = "distilbert-base-uncased"
MAX_LENGTH = 128          # capped for VRAM - most prompts fit comfortably
OUTPUT_DIR = "./checkpoints"
FINAL_MODEL_DIR = "./final_model"


def load_data():
    train_df = pd.read_csv("../data/train.csv")
    val_df = pd.read_csv("../data/val.csv")
    return Dataset.from_pandas(train_df[["text", "label"]]), Dataset.from_pandas(val_df[["text", "label"]])


def compute_metrics(eval_pred):
    logits, labels = eval_pred
    preds = np.argmax(logits, axis=-1)
    acc = accuracy_score(labels, preds)
    precision, recall, f1, _ = precision_recall_fscore_support(labels, preds, average="binary")
    return {"accuracy": acc, "precision": precision, "recall": recall, "f1": f1}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--resume", action="store_true", help="Resume training from last checkpoint")
    args = parser.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Using device: {device}")
    if device == "cuda":
        print(f"GPU: {torch.cuda.get_device_name(0)}")

    print("Loading data...")
    train_ds, val_ds = load_data()
    print(f"Train: {len(train_ds)} | Val: {len(val_ds)}")

    print(f"Loading tokenizer and model: {MODEL_NAME}")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME, num_labels=2)

    def tokenize_fn(batch):
        return tokenizer(batch["text"], truncation=True, padding="max_length", max_length=MAX_LENGTH)

    print("Tokenizing...")
    train_ds = train_ds.map(tokenize_fn, batched=True)
    val_ds = val_ds.map(tokenize_fn, batched=True)

    train_ds = train_ds.rename_column("label", "labels")
    val_ds = val_ds.rename_column("label", "labels")
    train_ds.set_format(type="torch", columns=["input_ids", "attention_mask", "labels"])
    val_ds.set_format(type="torch", columns=["input_ids", "attention_mask", "labels"])

    training_args = TrainingArguments(
        output_dir=OUTPUT_DIR,
        num_train_epochs=4,
        per_device_train_batch_size=8,       # small - fits 4GB VRAM
        per_device_eval_batch_size=8,
        gradient_accumulation_steps=4,       # effective batch size = 8*4 = 32
        learning_rate=2e-5,
        weight_decay=0.01,
        eval_strategy="epoch",
        save_strategy="epoch",
        save_total_limit=2,                  # keep only last 2 checkpoints on disk
        load_best_model_at_end=True,
        metric_for_best_model="f1",
        logging_dir="./logs",
        logging_steps=50,
        fp16=(device == "cuda"),             # mixed precision - saves VRAM on GPU
        report_to="none",
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        compute_metrics=compute_metrics,
    )

    print("\nStarting training...")
    if args.resume:
        print("Resuming from last checkpoint...")
        trainer.train(resume_from_checkpoint=True)
    else:
        trainer.train()

    print("\nEvaluating on validation set...")
    metrics = trainer.evaluate()
    print(metrics)

    print(f"\nSaving final model to {FINAL_MODEL_DIR}")
    trainer.save_model(FINAL_MODEL_DIR)
    tokenizer.save_pretrained(FINAL_MODEL_DIR)
    print("Done.")


if __name__ == "__main__":
    main()