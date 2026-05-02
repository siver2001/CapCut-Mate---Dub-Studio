from __future__ import annotations

import importlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from .config import DUB_STUDIO_DIR


def safe_print(*parts: Any, flush: bool = False, file: Any | None = None) -> None:
    kwargs: dict[str, Any] = {"flush": flush}
    if file is not None:
        kwargs["file"] = file
    try:
        print(*parts, **kwargs)
    except UnicodeEncodeError:
        target = file or sys.stdout
        buffer = getattr(target, "buffer", None)
        if buffer is not None:
            try:
                buffer.write((" ".join(str(part) for part in parts) + "\n").encode("utf-8"))
                if flush:
                    buffer.flush()
                return
            except (BrokenPipeError, OSError):
                return
            except Exception:
                pass
        safe_parts = [str(part).encode("ascii", errors="backslashreplace").decode("ascii") for part in parts]
        try:
            print(*safe_parts, **kwargs)
        except (BrokenPipeError, OSError):
            return
    except (BrokenPipeError, OSError):
        return


def emit(prefix: str, payload: dict[str, Any]) -> None:
    line = f"{prefix}::{json.dumps(payload, ensure_ascii=False)}"
    safe_print(line, flush=True)


def emit_progress(
    *,
    phase: str,
    step: str,
    progress: float,
    message: str,
    status: str = "running",
    extra: dict[str, Any] | None = None,
) -> None:
    payload = {
        "phase": phase,
        "step": step,
        "progress": round(max(0.0, min(progress, 1.0)), 4),
        "message": message,
        "status": status,
    }
    if extra:
        payload.update(extra)
    emit("PROGRESS", payload)


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def ensure_job_dirs(job_id: str) -> dict[str, Path]:
    job_root = ensure_dir(DUB_STUDIO_DIR / job_id)
    return {
        "root": job_root,
        "analysis": ensure_dir(job_root / "analysis"),
        "tts": ensure_dir(job_root / "tts"),
        "audio": ensure_dir(job_root / "audio"),
        "render": ensure_dir(job_root / "render"),
        "draft": ensure_dir(job_root / "draft"),
    }


def run(cmd: list[str], cwd: Path | None = None, capture_output: bool = False, timeout: float | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        check=True,
        text=True,
        capture_output=capture_output,
        encoding="utf-8",
        errors="ignore",
        timeout=timeout,
    )


def extract_audio_clip(input_path: Path, output_path: Path, start_ms: int, duration_ms: int) -> None:
    import shutil
    ffmpeg_exe = shutil.which("ffmpeg")
    if not ffmpeg_exe:
        mei = Path(getattr(sys, "_MEIPASS", ""))
        if mei:
            for cand in [mei / "tools" / "bin", mei / "internal" / "tools" / "bin"]:
                if (cand / "ffmpeg.exe").exists():
                    ffmpeg_exe = str(cand / "ffmpeg.exe")
                    break
    if not ffmpeg_exe:
        exe_dir = Path(sys.executable).parent
        for cand in [
            exe_dir / "tools" / "bin",
            exe_dir / "internal" / "tools" / "bin",
            exe_dir.parent / "tools" / "bin",
            exe_dir.parent / "internal" / "tools" / "bin"
        ]:
            if (cand / "ffmpeg.exe").exists():
                ffmpeg_exe = str(cand / "ffmpeg.exe")
                break
    if not ffmpeg_exe:
        for p in [Path("C:/ffmpeg/bin/ffmpeg.exe"), Path("C:/Program Files/ffmpeg/bin/ffmpeg.exe")]:
            if p.exists():
                ffmpeg_exe = str(p)
                break
    if not ffmpeg_exe:
        ffmpeg_exe = "ffmpeg"

    run(
        [
            ffmpeg_exe,
            "-y",
            "-ss",
            f"{max(start_ms, 0) / 1000:.3f}",
            "-i",
            str(input_path),
            "-t",
            f"{max(duration_ms, 100) / 1000:.3f}",
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            str(output_path),
        ]
    )


def run_output(cmd: list[str], cwd: Path | None = None, timeout: float | None = None) -> str:
    completed = run(cmd, cwd=cwd, capture_output=True, timeout=timeout)
    return completed.stdout.strip()


def module_available(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def ensure_python_packages(
    module_package_pairs: list[tuple[str, str]],
    *,
    phase: str,
    step: str,
    progress: float,
    message: str,
) -> None:
    missing_packages: list[str] = []
    seen_packages: set[str] = set()
    for module_name, package_name in module_package_pairs:
        if module_available(module_name):
            continue
        if package_name not in seen_packages:
            missing_packages.append(package_name)
            seen_packages.add(package_name)
    if not missing_packages:
        return
    emit_progress(
        phase=phase,
        step=step,
        progress=progress,
        message=message,
    )
    run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            *missing_packages,
        ]
    )
    importlib.invalidate_caches()
