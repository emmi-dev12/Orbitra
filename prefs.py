"""ORBITRA — local user preferences. Persists to ~/.orbitra/prefs.json."""

import json
from pathlib import Path

PREFS_DIR = Path.home() / ".orbitra"
PREFS_FILE = PREFS_DIR / "prefs.json"

_DEFAULT: dict = {
    "expansion_langs": [],          # [] = auto-detect from region; else list of lang codes
    "accuracy_goal": 50,            # last used accuracy goal
    "default_mode": None,           # "personal" / "research" / "leadgen" / None
    "default_profile": None,        # "light" / "medium" / "heavy" / None
}


def load() -> dict:
    if PREFS_FILE.exists():
        try:
            data = json.loads(PREFS_FILE.read_text())
            return {**_DEFAULT, **data}
        except Exception:
            pass
    return dict(_DEFAULT)


def save(prefs: dict):
    PREFS_DIR.mkdir(parents=True, exist_ok=True)
    PREFS_FILE.write_text(json.dumps(prefs, indent=2, ensure_ascii=False))


def get(key: str):
    return load().get(key, _DEFAULT.get(key))


def set_key(key: str, value):
    prefs = load()
    prefs[key] = value
    save(prefs)
