import asyncio
import json
import os
import sys
import threading
import webbrowser
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from werkzeug.utils import secure_filename


# ============================================================
# LOCAL CONFIGURATION
# ============================================================

CONFIG_DIR = Path(os.getenv("APPDATA", Path.home())) / "ReferenceAuthenticator"
CONFIG_FILE = CONFIG_DIR / "config.json"


def load_saved_config():
    """
    Load API keys saved by the first-launch configuration screen
    and place them into environment variables before backend.py
    is imported.
    """
    if not CONFIG_FILE.exists():
        return

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)

        # Groq
        if config.get("GROQ_API_KEY"):
            os.environ["GROQ_API_KEY"] = config["GROQ_API_KEY"]

        # Our config uses GEMINI_API_KEY,
        # while backend.py expects GOOGLE_API_KEY.
        if config.get("GEMINI_API_KEY"):
            os.environ["GOOGLE_API_KEY"] = config["GEMINI_API_KEY"]

        # Optional OpenAI key
        if config.get("OPENAI_API_KEY"):
            os.environ["OPENAI_API_KEY"] = config["OPENAI_API_KEY"]

        # Optional contact email
        if config.get("CONTACT_EMAIL"):
            os.environ["CONTACT_EMAIL"] = config["CONTACT_EMAIL"]

    except Exception:
        pass


# Load saved keys BEFORE backend.py is imported.
load_saved_config()


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent

# PyInstaller places bundled data in _MEIPASS.
if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    FRONTEND_DIR = Path(sys._MEIPASS) / "frontend"
else:
    FRONTEND_DIR = PROJECT_DIR / "frontend"

EXPORT_DIR = BASE_DIR / "exports"
EXPORT_DIR.mkdir(exist_ok=True)


# ============================================================
# LAZY BACKEND LOADING
# ============================================================

_backend = None


def get_backend():
    """
    Import backend.py only when it is actually needed.

    This is important because backend.py creates the AI provider
    chains when it is imported. On first launch, the user may not
    have entered API keys yet.
    """
    global _backend

    if _backend is None:
        from backend import (
            run_verification_system as _run_verification_system,
            run_batch_verification as _run_batch_verification,
            extract_references_from_text as _extract_references_from_text,
            extract_references_from_pdf as _extract_references_from_pdf,
            export_results_to_excel as _export_results_to_excel,
        )

        _backend = {
            "run_verification_system": _run_verification_system,
            "run_batch_verification": _run_batch_verification,
            "extract_references_from_text": _extract_references_from_text,
            "extract_references_from_pdf": _extract_references_from_pdf,
            "export_results_to_excel": _export_results_to_excel,
        }

    return _backend


# These wrapper functions keep the rest of server.py unchanged.


def run_verification_system(*args, **kwargs):
    return get_backend()["run_verification_system"](*args, **kwargs)


def run_batch_verification(*args, **kwargs):
    return get_backend()["run_batch_verification"](*args, **kwargs)


def extract_references_from_text(*args, **kwargs):
    return get_backend()["extract_references_from_text"](*args, **kwargs)


def extract_references_from_pdf(*args, **kwargs):
    return get_backend()["extract_references_from_pdf"](*args, **kwargs)


def export_results_to_excel(*args, **kwargs):
    return get_backend()["export_results_to_excel"](*args, **kwargs)


# ============================================================
# FLASK APP
# ============================================================

app = Flask(__name__, static_folder=None)

ALLOWED_EXTENSIONS = {"pdf"}


# ============================================================
# CONFIGURATION API
# ============================================================

@app.get("/api/config")
def get_config():
    """
    Tell the frontend whether API keys have already been saved.
    """
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)

            return jsonify({
                "configured": bool(
                    config.get("GROQ_API_KEY") or
                    config.get("GEMINI_API_KEY")
                )
            })

        except Exception:
            pass

    return jsonify({"configured": False})


@app.post("/api/config")
def save_config_api():
    """
    Save API keys locally on the user's computer.

    The keys are NOT stored in the application folder,
    GitHub repository, or installer.
    """
    data = request.get_json(silent=True) or {}

    config = {
        "GROQ_API_KEY": (data.get("GROQ_API_KEY") or "").strip(),
        "GEMINI_API_KEY": (data.get("GEMINI_API_KEY") or "").strip(),
        "OPENAI_API_KEY": (data.get("OPENAI_API_KEY") or "").strip(),
        "CONTACT_EMAIL": (data.get("CONTACT_EMAIL") or "").strip(),
    }

    # At least one AI provider must be configured.
    if not config["GROQ_API_KEY"] and not config["GEMINI_API_KEY"]:
        return jsonify(
            message="Please enter at least a Groq or Gemini API key."
        ), 400

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4)

    # Make the newly entered keys available immediately.
    # backend.py will read these when it is first imported.
    if config["GROQ_API_KEY"]:
        os.environ["GROQ_API_KEY"] = config["GROQ_API_KEY"]

    if config["GEMINI_API_KEY"]:
        os.environ["GOOGLE_API_KEY"] = config["GEMINI_API_KEY"]

    if config["OPENAI_API_KEY"]:
        os.environ["OPENAI_API_KEY"] = config["OPENAI_API_KEY"]

    if config["CONTACT_EMAIL"]:
        os.environ["CONTACT_EMAIL"] = config["CONTACT_EMAIL"]

    return jsonify({"success": True})


# ============================================================
# HELPERS
# ============================================================

def run_async(coro):
    return asyncio.run(coro)


def export_and_url(results, filename):
    path = EXPORT_DIR / filename
    export_results_to_excel(results, filename=str(path))
    return "/api/download/" + path.name


# ============================================================
# FRONTEND
# ============================================================

@app.get("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.get("/<path:path>")
def frontend_files(path):
    candidate = FRONTEND_DIR / path

    if candidate.exists() and candidate.is_file():
        return send_from_directory(FRONTEND_DIR, path)

    return send_from_directory(FRONTEND_DIR, "index.html")


# ============================================================
# SINGLE REFERENCE
# ============================================================

@app.post("/api/verify/single")
def verify_single_api():
    data = request.get_json(silent=True) or {}

    reference = (data.get("reference") or "").strip()

    if not reference:
        return jsonify(message="Please enter a reference."), 400

    result = run_async(run_verification_system(reference))
    results = [result]

    return jsonify(
        results=results,
        download_url=export_and_url(
            results,
            "single_reference_result.xlsx"
        )
    )


# ============================================================
# REFERENCE LIST
# ============================================================

@app.post("/api/verify/list")
def verify_list_api():
    data = request.get_json(silent=True) or {}

    text = (data.get("reference_text") or "").strip()

    if not text:
        return jsonify(message="Please enter a reference list."), 400

    references = extract_references_from_text(text)

    if not references:
        return jsonify(
            message="No references could be detected."
        ), 400

    results = run_async(run_batch_verification(references))

    return jsonify(
        results=results,
        download_url=export_and_url(
            results,
            "reference_verification_results.xlsx"
        )
    )


# ============================================================
# PDF
# ============================================================

@app.post("/api/verify/pdf")
def verify_pdf_api():
    if "file" not in request.files:
        return jsonify(message="Please select a PDF."), 400

    file = request.files["file"]

    if not file or not file.filename:
        return jsonify(message="Please select a PDF."), 400

    if (
        "." not in file.filename
        or file.filename.rsplit(".", 1)[1].lower()
        not in ALLOWED_EXTENSIONS
    ):
        return jsonify(message="Please upload a PDF file."), 400

    temp_path = EXPORT_DIR / secure_filename(file.filename)

    file.save(temp_path)

    try:
        references = extract_references_from_pdf(str(temp_path))

        if not references:
            return jsonify(
                message="No references could be extracted from this PDF."
            ), 400

        results = run_async(run_batch_verification(references))

        return jsonify(
            results=results,
            download_url=export_and_url(
                results,
                "pdf_reference_verification_results.xlsx"
            )
        )

    finally:
        try:
            temp_path.unlink(missing_ok=True)
        except Exception:
            pass


# ============================================================
# EXCEL DOWNLOAD
# ============================================================

@app.get("/api/download/<filename>")
def download(filename):
    return send_from_directory(
        EXPORT_DIR,
        filename,
        as_attachment=True
    )


# ============================================================
# OPEN BROWSER
# ============================================================

def open_browser():
    webbrowser.open("http://127.0.0.1:8000")


# ============================================================
# START SERVER
# ============================================================

if __name__ == "__main__":
    print(
        "Reference Authenticator running at "
        "http://127.0.0.1:8000",
        flush=True
    )

    if os.environ.get("REFERENCE_AUTH_NO_BROWSER") != "1":
        threading.Timer(1.2, open_browser).start()

    app.run(
        host="127.0.0.1",
        port=8000,
        debug=False,
        use_reloader=False
    )
