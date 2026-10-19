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
from typing import Optional, List

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv()

# --- Import the ML fusion engine from ../ml and local modules from backend ---
sys.path.append(os.path.dirname(__file__))
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "ml"))
from fusion_engine import FusionEngine
from llm_provider import get_provider, OllamaProvider

DB_PATH = os.path.join(os.path.dirname(__file__), "shield_llm.db")

# --- Global engine & gateway instances, loaded once at startup ---
engine = None
llm_gateway = None

CATEGORY_DESCRIPTIONS = {
    "instruction_override": "an instruction override attempt",
    "prompt_extraction": "requests disclosure of hidden system instructions",
    "role_confusion": "a persona manipulation or jailbreak pattern (e.g. DAN mode)",
    "delimiter_injection": "a system delimiter injection marker",
    "obfuscation": "an encoded or obfuscated adversarial payload",
    "social_engineering": "an adversarial social engineering pretext",
}


def generate_security_explanation(
    verdict: str,
    clf_score: float,
    sem_score: float,
    rules_score: float,
    categories: List[str]
) -> str:
    """
    Derives clear, human-readable explanations strictly from actual detector findings.
    Does not invent attack categories. Explicitly states forwarding status.
    """
    if verdict == "malicious":
        if categories:
            cat_descs = [CATEGORY_DESCRIPTIONS.get(c, c) for c in categories]
            if len(cat_descs) == 1:
                reasons = cat_descs[0]
            elif len(cat_descs) == 2:
                reasons = f"{cat_descs[0]} and {cat_descs[1]}"
            else:
                reasons = ", ".join(cat_descs[:-1]) + f", and {cat_descs[-1]}"
            return (
                f"Blocked because the input contains {reasons}. "
                f"Security gateway detected high-risk patterns (Rule severity: {rules_score:.2f}, "
                f"Classifier threat probability: {clf_score:.1%}). Prompt not forwarded to LLM."
            )
        elif sem_score >= 0.45:
            return (
                f"Blocked because the input exhibits high semantic similarity ({sem_score:.1%}) "
                f"to known adversarial prompt injection attacks. Prompt not forwarded to LLM."
            )
        else:
            return (
                f"Blocked because the deep learning classifier detected high-confidence prompt injection "
                f"characteristics (threat probability: {clf_score:.1%}). Prompt not forwarded to LLM."
            )

    elif verdict == "suspicious":
        if categories:
            cat_descs = [CATEGORY_DESCRIPTIONS.get(c, c) for c in categories]
            return (
                f"Review required: The prompt matched borderline pattern(s): {', '.join(cat_descs)} "
                f"(risk score: {rules_score:.2f}). Prompt not forwarded to LLM pending review."
            )
        return (
            f"Review required: The prompt exhibited ambiguous or borderline injection indicators "
            f"(threat score: {clf_score:.2f}). Prompt not forwarded to LLM pending review."
        )

    else:  # safe
        return (
            "Prompt cleared: No adversarial directives, prompt extraction requests, or jailbreak patterns "
            "detected across rules, semantic analysis, or classifier. Cleared and forwarded to Local LLM (Gemma)."
        )


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
    # Check if forwarded_to_llm column exists; add if missing
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(prompt_logs)")
    columns = [row[1] for row in cursor.fetchall()]
    if "forwarded_to_llm" not in columns:
        try:
            conn.execute("ALTER TABLE prompt_logs ADD COLUMN forwarded_to_llm INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass
    conn.commit()
    conn.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global engine, llm_gateway
    model_dir = os.environ.get(
        "SHIELD_MODEL_DIR",
        os.path.join(os.path.dirname(__file__), "..", "ml", "models", "distilbert_phase5d"),
    )
    train_csv = os.environ.get(
        "SHIELD_TRAIN_CSV",
        os.path.join(os.path.dirname(__file__), "..", "data", "train_phase5g.csv"),
    )
    print(f"Loading fusion engine (model: {model_dir})...")
    print(f"Semantic reference bank: {train_csv}")
    engine = FusionEngine(
        model_dir=model_dir,
        train_csv=train_csv,
    )
    engine.load()
    init_db()

    # Initialize the LLM Gateway adapter (defaults to local Ollama gemma3:1b)
    llm_gateway = get_provider()
    if isinstance(llm_gateway, OllamaProvider):
        avail, reason = llm_gateway.is_available()
        if avail:
            print(f"Ollama Gateway ready: connected to {llm_gateway.model} at {llm_gateway.base_url}")
        else:
            print(f"Ollama Gateway warning: {reason}")
    else:
        print(f"LLM Gateway configured with model: {getattr(llm_gateway, 'model', 'default')}")

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


def log_prompt(text: str, verdict: str, confidence: float, categories: list, forwarded: int = 0):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(prompt_logs)")
    columns = [row[1] for row in cursor.fetchall()]

    if "forwarded_to_llm" in columns:
        conn.execute(
            "INSERT INTO prompt_logs (prompt_text, verdict, confidence, categories, created_at, forwarded_to_llm) VALUES (?, ?, ?, ?, ?, ?)",
            (text, verdict, confidence, ",".join(categories), datetime.utcnow().isoformat(), forwarded),
        )
    else:
        conn.execute(
            "INSERT INTO prompt_logs (prompt_text, verdict, confidence, categories, created_at) VALUES (?, ?, ?, ?, ?)",
            (text, verdict, confidence, ",".join(categories), datetime.utcnow().isoformat()),
        )
    conn.commit()
    conn.close()


@app.post("/analyze")
def analyze_prompt(request: PromptRequest):
    result = engine.analyze(request.text)

    verdict = result["verdict"]
    combined_score = result["combined_score"]
    clf_score = result["detectors"]["classifier"]
    sem_score = result["detectors"]["semantic"]
    rules_dict = result["detectors"]["rules"]
    rules_score = rules_dict["weight"]
    categories = rules_dict["categories"]

    # Generate human-readable security explanation from actual findings
    security_explanation = generate_security_explanation(
        verdict=verdict,
        clf_score=clf_score,
        sem_score=sem_score,
        rules_score=rules_score,
        categories=categories,
    )

    forwarded_to_llm = False
    llm_response = None
    llm_error = None

    # =========================================================================
    # CRITICAL SERVER-SIDE SECURITY GATEWAY ROUTING
    # Only prompts with verdict == 'safe' are allowed to be forwarded to the LLM.
    # MALICIOUS and SUSPICIOUS prompts are strictly blocked on the backend.
    # =========================================================================
    if verdict == "safe":
        forwarded_to_llm = True
        llm_response, llm_error = llm_gateway.generate_response(request.text)
    elif verdict == "malicious":
        forwarded_to_llm = False
        llm_response = None
        llm_error = None
    else:  # suspicious
        forwarded_to_llm = False
        llm_response = None
        llm_error = None

    # SQLite prompt logging
    log_prompt(
        text=request.text,
        verdict=verdict,
        confidence=combined_score,
        categories=categories,
        forwarded=1 if forwarded_to_llm else 0,
    )

    # Return structured schema required by gateway specification
    return {
        "verdict": verdict,
        "combined_score": combined_score,
        "classifier_score": clf_score,
        "semantic_score": sem_score,
        "rules_score": rules_score,
        "matched_rules": categories,
        "security_explanation": security_explanation,
        "forwarded_to_llm": forwarded_to_llm,
        "llm_response": llm_response,
        "llm_error": llm_error,
        "llm_provider": getattr(llm_gateway, "provider_name", "Ollama (Local)"),
        "llm_model": getattr(llm_gateway, "model", "gemma3:1b"),
        # Preserve legacy fields for 100% backward compatibility
        "detectors": result["detectors"],
        "fusion_mode": result.get("fusion_mode"),
        "explanation": security_explanation,
    }


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
