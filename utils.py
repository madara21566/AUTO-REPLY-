# utils.py
from pathlib import Path
import json
import os
from datetime import datetime

ROOT_DIR = Path(".").resolve()
USERS_DIR = ROOT_DIR / "users"
DATA_DIR = ROOT_DIR / "data"
BACKUPS_DIR = ROOT_DIR / "backups"

USERS_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)
BACKUPS_DIR.mkdir(parents=True, exist_ok=True)

def load_json(path: Path, default):
    try:
        if path.exists():
            return json.loads(path.read_text())
    except Exception:
        pass
    return default

def save_json(path: Path, data):
    try:
        path.write_text(json.dumps(data, indent=2))
    except Exception:
        pass

def ensure_user_record(uid: int):
    users_file = DATA_DIR / "users.json"
    users = load_json(users_file, {})
    if str(uid) not in users:
        users[str(uid)] = {"projects": [], "password": None}
        save_json(users_file, users)

def now_ts():
    return datetime.utcnow().isoformat()
