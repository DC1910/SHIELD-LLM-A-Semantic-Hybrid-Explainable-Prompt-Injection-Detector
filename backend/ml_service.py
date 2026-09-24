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

    model_dir = os.path.join(ML_DIR, "final_model")
    train_csv = os.path.abspath(
        os.path.join(ML_DIR, "..", "data", "train.csv")
    )

    engine = FusionEngine(
        model_dir=model_dir,
        train_csv=train_csv
    )

    engine.load()

    return engine