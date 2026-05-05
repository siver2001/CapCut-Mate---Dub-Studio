from __future__ import annotations

import json
import subprocess
from dataclasses import asdict
from pathlib import Path

import srt

from .config import TEMP_DIR
from .models import ClipManifest


def run(cmd: list[str], cwd: Path | None = None) -> None:
    import sys
    creationflags = 0
    if sys.platform == "win32":
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    print(">", " ".join(str(part) for part in cmd))
    subprocess.run(cmd, check=True, cwd=str(cwd) if cwd else None, creationflags=creationflags)


def run_output(cmd: list[str]) -> str:
    import sys
    creationflags = 0
    if sys.platform == "win32":
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    result = subprocess.run(cmd, check=True, capture_output=True, text=True, creationflags=creationflags)
    return result.stdout.strip()


def ffprobe_duration_ms(path: Path) -> int:
    value = run_output(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ]
    )
    return int(float(value) * 1000)


def ensure_workspace() -> None:
    for folder in [TEMP_DIR, TEMP_DIR / "tts_clips", TEMP_DIR / "logs"]:
        folder.mkdir(parents=True, exist_ok=True)


def load_srt(path: Path) -> list[srt.Subtitle]:
    content = path.read_text(encoding="utf-8", errors="ignore")
    return list(srt.parse(content))


def save_srt(path: Path, subtitles: list[srt.Subtitle]) -> None:
    path.write_text(srt.compose(subtitles), encoding="utf-8")


def load_manual_lines(path: Path) -> list[str]:
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines()]
    return [line for line in lines if line]


def write_manifest(manifest: list[ClipManifest]) -> None:
    output = TEMP_DIR / "dub_manifest.json"
    output.write_text(
        json.dumps([asdict(item) for item in manifest], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
