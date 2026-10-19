"""
run_demo.py
Convenience launcher to start both the FastAPI backend and React frontend concurrently.
"""
import os
import sys
import time
import subprocess

ROOT_DIR = os.path.abspath(os.path.dirname(__file__))

def main():
    print("=" * 65)
    print("       SHIELD-LLM LIVE DEMONSTRATION LAUNCHER")
    print("=" * 65)

    python_exe = os.path.join(ROOT_DIR, "ml", "venv", "Scripts", "python.exe")
    if not os.path.exists(python_exe):
        python_exe = sys.executable

    print("\n[1/2] Starting FastAPI Backend on http://localhost:8000 ...")
    backend_proc = subprocess.Popen(
        [python_exe, "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"],
        cwd=ROOT_DIR
    )

    print("[2/2] Waiting for ML models to load (5 seconds)...")
    time.sleep(5)

    print("Starting React Frontend on http://localhost:5173 ...")
    frontend_proc = subprocess.Popen(
        ["npm", "run", "dev"],
        shell=True,
        cwd=ROOT_DIR
    )

    print("\n" + "=" * 65)
    print("SHIELD-LLM is live:")
    print("  * Web Dashboard:  http://localhost:5173")
    print("  * API Swagger UI: http://localhost:8000/docs")
    print("Press Ctrl+C to terminate both servers.")
    print("=" * 65 + "\n")

    try:
        backend_proc.wait()
        frontend_proc.wait()
    except KeyboardInterrupt:
        print("\nShutting down SHIELD-LLM demo servers...")
        backend_proc.terminate()
        frontend_proc.terminate()
        print("Shutdown complete.")

if __name__ == "__main__":
    main()
