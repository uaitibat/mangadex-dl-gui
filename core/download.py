"""Helpers de download - parsing e sanitização."""

from __future__ import annotations

import re
from pathlib import Path


def safe_folder_name(value: str, max_len: int = 255) -> str:
    cleaned = "".join(c if c not in '<>:"/\\|?*' else "_" for c in value)
    cleaned = cleaned.strip().strip(".")
    if not cleaned:
        cleaned = "MangaDex"
    # truncar para limite de filesystem (255)
    if len(cleaned) > max_len:
        cleaned = cleaned[:max_len].rstrip(" .")
    return cleaned


def build_download_command(command: str, url: str, manga_folder: Path) -> list[str]:
    return [
        command,
        "--type",
        "chapter",
        "--path",
        str(manga_folder),
        "--replace",
        "--progress-bar-layout",
        "none",
        url,
    ]


# regex pré-compilados para performance
_RE_FRAC = re.compile(r"(\d+)\s*/\s*(\d+)")
_RE_PAGE = re.compile(r"p[aá]g(?:ina)?\D+(\d+)", re.IGNORECASE)
_RE_FINISHED = re.compile(r"finished\s+download\s+chapter", re.IGNORECASE)
_RE_ERROR = re.compile(r"(error|failed|exception)", re.IGNORECASE)


def is_finished_line(line: str) -> bool:
    return bool(_RE_FINISHED.search(line))


def is_error_line(line: str) -> bool:
    return bool(_RE_ERROR.search(line))


def parse_progress(line: str) -> tuple[str | None, str | None]:
    """Retorna (current, total) se encontrar fração, senão (page, None)."""
    m = _RE_FRAC.search(line)
    if m:
        return m.group(1), m.group(2)
    m2 = _RE_PAGE.search(line)
    if m2:
        return m2.group(1), None
    return None, None
