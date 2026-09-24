"""
main.py - SHIELD-LLM backend API
Minimal, deadline-scoped version: no external LLM calls, SQLite for logging.
Wraps the ML fusion engine and exposes it to the frontend.

Run:
    uvicorn main:app --reload --port 8000

Then test at http://localhost:8000/docs
"""

import sys
import os
import sqlite3
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# --- Import the ML fusion engine from ../ml ---
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "ml"))
from fusion_engine import FusionEngine

DB_PATH = "shield_llm.db"

# --- Global engine instance, loaded once at startup ---
engine = None


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS prompt_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prompt_text TEXT,
            verdict TEXT,
            confidence REAL,
            categories TEXT,
            created_at TEXT
        )
    """)
    conn.commit()
    conn.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global engine
    print("Loading fusion engine (one-time startup cost)...")
    engine = FusionEngine(
        model_dir=os.path.join(os.path.dirname(__file__), "..", "ml", "final_model"),
        train_csv=os.path.join(os.path.dirname(__file__), "..", "data", "train.csv"),
    )
    engine.load()
    init_db()
    print("Backend ready.")
    yield


app = FastAPI(lifespan=lifespan)

# Allow the frontend (running on a different port) to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # fine for a local demo; tighten later if needed
    allow_methods=["*"],
    allow_headers=["*"],
)


class PromptRequest(BaseModel):
    text: str


def log_prompt(text, verdict, confidence, categories):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO prompt_logs (prompt_text, verdict, confidence, categories, created_at) VALUES (?, ?, ?, ?, ?)",
        (text, verdict, confidence, ",".join(categories), datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()


@app.post("/analyze")
def analyze_prompt(request: PromptRequest):
    result = engine.analyze(request.text)

    categories = result["detectors"]["rules"]["categories"]
    log_prompt(request.text, result["verdict"], result["combined_score"], categories)

    # No real LLM call - placeholder response for "safe" verdicts
    if result["verdict"] == "safe":
        result["llm_response"] = "[This is where the actual LLM's response would appear. The prompt passed all security checks.]"
    else:
        result["llm_response"] = None

    return result


@app.get("/logs")
def get_logs(limit: int = 20):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM prompt_logs ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


@app.get("/stats")
def get_stats():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    total = conn.execute("SELECT COUNT(*) as c FROM prompt_logs").fetchone()["c"]
    safe = conn.execute("SELECT COUNT(*) as c FROM prompt_logs WHERE verdict='safe'").fetchone()["c"]
    suspicious = conn.execute("SELECT COUNT(*) as c FROM prompt_logs WHERE verdict='suspicious'").fetchone()["c"]
    malicious = conn.execute("SELECT COUNT(*) as c FROM prompt_logs WHERE verdict='malicious'").fetchone()["c"]

    # Category breakdown
    rows = conn.execute("SELECT categories FROM prompt_logs WHERE categories != ''").fetchall()
    category_counts = {}
    for row in rows:
        for cat in row["categories"].split(","):
            if cat:
                category_counts[cat] = category_counts.get(cat, 0) + 1

    conn.close()

    return {
        "total_scans": total,
        "safe": safe,
        "suspicious": suspicious,
        "malicious": malicious,
        "attack_categories": category_counts,
    }


@app.get("/")
def root():
    return {"status": "SHIELD-LLM backend running"}
