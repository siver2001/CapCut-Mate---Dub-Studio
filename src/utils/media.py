import subprocess
import os
from typing import Optional
from src.utils.logger import logger


def get_media_duration(file_path: str) -> Optional[int]:
    """
    Get media duration in microseconds using ffprobe.
    
    Args:
        file_path: Path to the media file.
        
    Returns:
        Optional[int]: Duration in microseconds, or None if failed.
    """
    if not os.path.exists(file_path):
        logger.warning(f"File not found: {file_path}")
        return None

    try:
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            file_path
        ]
        
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30
        )

        if result.returncode != 0:
            logger.error(f"ffprobe failed: {result.stderr}")
            return None

        duration_str = result.stdout.strip()
        if not duration_str:
            return None

        # Convert to microseconds
        duration_seconds = float(duration_str)
        return int(duration_seconds * 1_000_000)

    except (subprocess.TimeoutExpired, ValueError, Exception) as e:
        logger.error(f"Failed to get media duration for {file_path}: {str(e)}")
        return None


def get_media_duration_formatted(file_path: str) -> Optional[str]:
    """
    Get formatted duration string (HH:MM:SS.mmm).
    """
    duration_us = get_media_duration(file_path)
    if duration_us is None:
        return None

    total_seconds = duration_us / 1_000_000
    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)
    seconds = int(total_seconds % 60)
    milliseconds = int((total_seconds % 1) * 1000)

    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{milliseconds:03d}"
