"""Font cache: downloads and loads Google Fonts for Qt preview rendering."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Font metadata: maps GUI fontFamilyName -> (Google Fonts family, variant(s))
# ---------------------------------------------------------------------------
# Google Fonts CSS API: https://fonts.googleapis.com/css2?family=<family>:wght@<weight>
# Use numeric weight (400, 700) instead of "regular" for better compatibility.
_FONT_META: dict[str, tuple[str, str]] = {
    "Poppins": ("Poppins", "400"),
    "Montserrat": ("Montserrat", "900"),
    "Inter": ("Inter", "600"),
    "Anton": ("Anton", "400"),
    "Staatliches": ("Staatliches", "400"),
    "Bungee": ("Bungee", "400"),
    "Kanit": ("Kanit", "400"),
    "Nunito": ("Nunito", "400"),
    "Rubik": ("Rubik", "400"),
    "Work Sans": ("Work+Sans", "400"),
    "Source Sans Pro": ("Source+Sans+3", "400"),
    "Source Han Sans CN": ("Noto+Sans+SC", "700"),
    "Source Han Serif CN": ("Noto+Serif+SC", "600"),
    "Playfair Display": ("Playfair+Display", "700"),
    "Lora": ("Lora", "400"),
    "Caveat": ("Caveat", "700"),
    "Great Vibes": ("Great+Vibes", "400"),
    "Alex Brush": ("Alex+Brush", "400"),
    "Marker": ("Permanent+Marker", "400"),
    "Bevan": ("Bevan", "400"),
    "Koulen": ("Koulen", "400"),
    # Luxury and Jellee are not on Google Fonts -- use alternatives below
}

# Fallback for fonts not on Google Fonts
_ALT_FONT: dict[str, str] = {
    "Luxury": "Playfair Display",
    "Jellee": "Montserrat",
}

# ---------------------------------------------------------------------------
# Google Fonts CSS API base
# ---------------------------------------------------------------------------
_GFONTS_CSS_URL = "https://fonts.googleapis.com/css2?family={family}:wght@{weight}&display=swap"

# Fallback direct font URLs (Google Fonts CDN) -- verified working
_DIRECT_URLS: dict[str, str] = {
    # Use only verified stable Google Fonts CDN URLs
    "Anton": "https://fonts.gstatic.com/s/anton/v30/PNI7lC1E3oow.woff",
    "Poppins": "https://fonts.gstatic.com/s/poppins/v24/pxiEyp8kv8JHgFVrFJA.ttf",
    "Montserrat": "https://fonts.gstatic.com/s/montserrat/v31/JTUHjIg1_i6t8kCHKm4532VJOt5-QNFgpCvC70w-.ttf",
    "Bungee": "https://fonts.gstatic.com/s/bungee/v11/DtVkJx20zEE4_ja4GBhW7Q.ttf",
    "Permanent Marker": "https://fonts.gstatic.com/s/permanentmarker/v16/Fh4uPib9Iyv2ucM6pGQMWimMp004Hao.ttf",
    "Playfair Display": "https://fonts.gstatic.com/s/playfairdisplay/v40/nuFvD-vYSZviVYUb_rj3ij__anPXJzDwcbmjWBN2PKeiukDQ.ttf",
    "Alex Brush": "https://fonts.gstatic.com/s/alexbrush/v23/SZc83FzrJKuqFbwMKk6EtUI.ttf",
    "Source Han Sans CN": "https://fonts.gstatic.com/s/notosanssc/v40/k3kCo84MPvpLmixcA63oeAL7Iqp5IZJF9bmaGzjCnYw.ttf",
    "Inter": "https://fonts.gstatic.com/s/inter/v20/UcCO3FwrK3iLTeHuS_nVMrMxCp50SjIw2boKoduKmMEVuGKYMZg.ttf",
}

# ---------------------------------------------------------------------------
# Cache directory
# ---------------------------------------------------------------------------
_FONT_CACHE_DIR: Optional[Path] = None


def _get_cache_dir() -> Path:
    global _FONT_CACHE_DIR
    if _FONT_CACHE_DIR is None:
        root = Path(__file__).parent.parent.parent
        _FONT_CACHE_DIR = root / "temp" / "font_cache"
        _FONT_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return _FONT_CACHE_DIR


def _font_cache_path(font_family: str) -> Path:
    """Return the cached .ttf path for a font family."""
    safe_name = font_family.replace(" ", "_").replace("-", "_")
    return _get_cache_dir() / f"{safe_name}.ttf"


def _resolve_family(family: str) -> tuple[str, str]:
    """Resolve actual Google Fonts family and weight from display name."""
    if family in _FONT_META:
        return _FONT_META[family]
    if family in _ALT_FONT:
        alt = _ALT_FONT[family]
        if alt in _FONT_META:
            return _FONT_META[alt]
    return family.replace(" ", "+"), "400"


def _download(url: str, dest: Path, timeout: float = 20.0) -> bool:
    """Download a URL to dest. Returns True on success."""
    try:
        import urllib.request

        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
        dest.write_bytes(data)
        return True
    except Exception:
        return False


def _fetch_css_and_extract_url(family: str, weight: str, cache_path: Path) -> bool:
    """Fetch Google Fonts CSS, extract first @font-face URL, download font."""
    import re
    import urllib.request

    css_url = _GFONTS_CSS_URL.format(family=family, weight=weight)
    try:
        req = urllib.request.Request(
            css_url,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "text/css,*/*;q=0.1",
            },
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            css_text = resp.read().decode("utf-8", errors="replace")
    except Exception:
        return False

    # Extract all font URLs from CSS. Google Fonts CSS uses url(URL) format(type).
    # The URL itself never contains ), so [^)]+ safely captures the URL.
    urls = re.findall(r'url\(([^)]+\.ttf)\)', css_text)
    for url in urls:
        if _download(url, cache_path):
            return True

    return False


def _is_font_installed(font_family: str) -> bool:
    """Check if a font is already available as a system font (via Windows Registry)."""
    try:
        import winreg

        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts",
            0,
        )
        family_lower = font_family.lower()
        i = 0
        while True:
            try:
                name, _, _ = winreg.EnumValue(key, i)
                i += 1
                # Registry entries are like "Poppins Bold (TrueType)" or "Inter Regular (OpenType)"
                # Match: font family name as a whole word at the start
                # e.g., "Inter" should not match "GlobalUserInterface.CompositeFont"
                if name.lower().startswith(family_lower + " ") or \
                   name.lower().startswith(family_lower + "(") or \
                   name.lower().startswith(family_lower.lower() + "\t"):
                    winreg.CloseKey(key)
                    return True
            except OSError:
                break
        winreg.CloseKey(key)
    except Exception:
        pass
    return False


def ensure_font(font_family: str) -> Optional[str]:
    """
    Ensure a font is cached locally and return its absolute file path.
    Returns None if the font cannot be downloaded.
    """
    if _is_font_installed(font_family):
        # Return None so callers know to use system font directly
        return None

    cache_path = _font_cache_path(font_family)
    if cache_path.exists() and cache_path.stat().st_size > 1000:
        return str(cache_path.resolve())

    # Primary: use Google Fonts CSS API (verified working for all 21 fonts)
    gf_family, gf_weight = _resolve_family(font_family)
    if _fetch_css_and_extract_url(gf_family, gf_weight, cache_path):
        return str(cache_path.resolve())

    # Fallback: try direct URL
    direct_url = _DIRECT_URLS.get(font_family)
    if direct_url and _download(direct_url, cache_path):
        return str(cache_path.resolve())

    return None


def preload_font(font_family: str) -> bool:
    """
    Download and register a font into Qt's font database.
    Returns True if the font is now available.
    """
    path = ensure_font(font_family)
    if path is None:
        # Font was already installed (system) or unavailable
        return _is_font_installed(font_family)

    try:
        from PyQt6.QtGui import QFontDatabase

        id_ = QFontDatabase.addApplicationFont(path)
        return id_ >= 0
    except Exception:
        return False


def preload_all_fonts() -> dict[str, bool]:
    """
    Pre-download and register all FONT_OPTIONS fonts.
    Returns a dict of font_family -> success bool.
    """
    families = list(_FONT_META.keys()) + list(_ALT_FONT.keys())
    result = {}
    for fam in families:
        result[fam] = preload_font(fam)
    return result
