import sys
import os

# Add the project's ml directory to Python's import path
ML_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "ml")
)

sys.path.append(ML_DIR)


def get_engine():
    """
    Creates and loads the SHIELD-LLM FusionEngine.

    The actual ML artifacts (final_model and training CSV)
    must be present before the engine can be loaded.
    """

    from fusion_engine import FusionEngine

    model_dir = os.environ.get(
        "SHIELD_MODEL_DIR",
        os.path.join(ML_DIR, "models", "distilbert_phase5d")
    )
    train_csv = os.environ.get(
        "SHIELD_TRAIN_CSV",
        os.path.abspath(os.path.join(ML_DIR, "..", "data", "train_phase5g.csv"))
    )

    engine = FusionEngine(
        model_dir=model_dir,
        train_csv=train_csv
    )

    engine.load()

    return engine