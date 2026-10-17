"""Shared locations for local and Railway runtime data."""

import os
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent
_configured_data_dir = os.environ.get("DATA_DIR")
DATA_DIR = Path(_configured_data_dir).expanduser() if _configured_data_dir else PROJECT_DIR
if not DATA_DIR.is_absolute():
    DATA_DIR = PROJECT_DIR / DATA_DIR
DATA_DIR.mkdir(parents=True, exist_ok=True)


def data_path(filename: str) -> str:
    return str(DATA_DIR / filename)
