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


from contextlib import contextmanager

@contextmanager
def safe_ffmpeg_path(path: Path, is_output: bool = False):
    """
    Ensures a path is relative to ROOT and has no spaces/colons,
    which is required to avoid syntax errors in FFmpeg filter graphs on Windows.
    If the path is on a different drive, outside ROOT, or contains spaces,
    it redirects via a space-free temporary file inside ROOT/temp/ffmpeg_temp.
    Yields: relative_path_as_posix
    """
    import uuid
    import shutil
    from .config import ROOT
    temp_file = None
    try:
        # Resolve path to absolute first
        abs_path = path.resolve()
    except Exception:
        abs_path = path.absolute()
        
    try:
        rel_path = abs_path.relative_to(ROOT)
        has_spaces = " " in rel_path.as_posix()
        if not has_spaces:
            yield rel_path.as_posix()
            return
    except ValueError:
        pass

    temp_dir = ROOT / "temp" / "ffmpeg_temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_file = temp_dir / f"{uuid.uuid4().hex}{path.suffix}"
    
    if not is_output and abs_path.exists():
        shutil.copy2(abs_path, temp_file)
        
    yield temp_file.relative_to(ROOT).as_posix()
    
    if is_output and temp_file.exists():
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(temp_file, abs_path)
        
    if temp_file and temp_file.exists():
        try:
            temp_file.unlink()
        except Exception:
            pass

