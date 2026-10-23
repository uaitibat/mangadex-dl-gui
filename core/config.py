"""Gerenciamento de configuração XDG-compliant."""

from __future__ import annotations

import json
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
LEGACY_CONFIG_PATH = BASE_DIR / "config.json"
XDG_CONFIG_HOME = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
CONFIG_DIR = XDG_CONFIG_HOME / "mangadex_dl"
CONFIG_PATH = Path(os.environ.get("MANGADEX_DL_CONFIG", str(CONFIG_DIR / "config.json")))


def load_config() -> dict:
    path = CONFIG_PATH if CONFIG_PATH.exists() else LEGACY_CONFIG_PATH
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def save_config(config: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(config, indent=2, ensure_ascii=True), encoding="utf-8")
    try:
        CONFIG_PATH.chmod(0o600)
    except OSError:
        pass
