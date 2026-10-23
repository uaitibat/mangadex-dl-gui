"""Cache helpers with TTL cleanup."""

from __future__ import annotations

import shutil
import time
from pathlib import Path
import tempfile

BASE_DIR = Path(__file__).resolve().parent.parent
ASSET_DIR = BASE_DIR / "assets"
CACHE_ROOT = Path(tempfile.gettempdir()) / "mangadex_dl_cache"
CUSTOM_WALLPAPER_DIR = CACHE_ROOT / "wallpapers"
PROFILE_CACHE_DIR = CACHE_ROOT / "profile"
READER_CACHE_DIR = CACHE_ROOT / "reader"
COVER_CACHE_DIR = ASSET_DIR / "covers"
# TTL: 7 dias para cache volátil (reader/profile/wallpaper)
CACHE_TTL_SECONDS = 7 * 24 * 3600


def ensure_cache_dirs() -> None:
    for p in (CUSTOM_WALLPAPER_DIR, PROFILE_CACHE_DIR, READER_CACHE_DIR, COVER_CACHE_DIR):
        p.mkdir(parents=True, exist_ok=True)


def clear_expired_cache() -> None:
    """Remove apenas arquivos expirados (>TTL) ao invés de apagar tudo no exit."""
    now = time.time()
    for cache_dir in (PROFILE_CACHE_DIR, READER_CACHE_DIR, CUSTOM_WALLPAPER_DIR):
        if not cache_dir.exists():
            continue
        for item in cache_dir.rglob("*"):
            try:
                if item.is_file() and (now - item.stat().st_mtime) > CACHE_TTL_SECONDS:
                    item.unlink()
                elif item.is_dir() and not any(item.iterdir()):
                    item.rmdir()
            except OSError:
                pass


def clear_volatile_cache() -> None:
    """Limpeza total - usado apenas manualmente."""
    for path in (PROFILE_CACHE_DIR, READER_CACHE_DIR, CUSTOM_WALLPAPER_DIR):
        try:
            if path.exists():
                shutil.rmtree(path)
        except OSError:
            pass
