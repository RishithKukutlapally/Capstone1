import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_FILE = PROJECT_ROOT / "config" / "config.yaml"

class Config:
    def __init__(self, data: dict):
        for key, value in data.items():
            setattr(self, key, Config(value) if isinstance(value, dict) else value)

_config = None

def get_config() -> Config:
    global _config
    if _config is None:
        load_dotenv(PROJECT_ROOT / ".env")
        text = CONFIG_FILE.read_text(encoding="utf-8")
        _config = Config(yaml.safe_load(text))
    return _config

def project_path(relative: str) -> Path:
    return PROJECT_ROOT / relative

def get_api_key() -> str:
    load_dotenv(PROJECT_ROOT / ".env")

    key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not key:
        raise RuntimeError(
            "No API key found. Copy .env.example to .env and set GOOGLE_API_KEY "
            "(or GEMINI_API_KEY) to your Google Gemini key."
        )
    return key
