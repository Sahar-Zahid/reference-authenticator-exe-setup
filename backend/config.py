import json
import os
from pathlib import Path

CONFIG_DIR = Path(os.getenv("APPDATA", Path.home())) / "ReferenceAuthenticator"
CONFIG_FILE = CONFIG_DIR / "config.json"


def load_config():
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    return {}


def save_config(config):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4)


config = load_config()

GROQ_API_KEY = config.get("GROQ_API_KEY", "")
GEMINI_API_KEY = config.get("GEMINI_API_KEY", "")
OPENAI_API_KEY = config.get("OPENAI_API_KEY", "")
CONTACT_EMAIL = config.get(
    "CONTACT_EMAIL",
    "your-email@example.com"
)
