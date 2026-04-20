import os
from typing import List, Tuple
from src.utils.logger import logger
from src.utils.download import download
from src.utils.media import get_media_duration
from exceptions import CustomException, CustomError
import config


def audio_timelines(links: List[str]) -> Tuple[List[dict], List[dict]]:
    """
    Calculate timeline split points based on audio file durations.
    
    Args:
        links: List of audio file URLs.
        
    Returns:
        tuple: (timelines, all_timelines) where timelines contains individual segment ranges.
    """
    logger.info(f"audio_timelines called with {len(links)} audio files")

    if not links:
        return [], [{"start": 0, "end": 0}]

    temp_files = []
    durations = []

    try:
        for i, link in enumerate(links):
            try:
                temp_file_path = download(link, config.TEMP_DIR)
                temp_files.append(temp_file_path)

                duration_us = get_media_duration(temp_file_path)
                if duration_us is None:
                    raise CustomException(CustomError.AUDIO_DURATION_GET_FAILED)

                durations.append(duration_us)
            except Exception as e:
                logger.error(f"Error processing audio file {link}: {str(e)}")
                raise CustomException(CustomError.AUDIO_DURATION_GET_FAILED)

        return _calculate_timelines(durations)

    finally:
        _cleanup_temp_files(temp_files)


def _calculate_timelines(durations: List[int]) -> Tuple[List[dict], List[dict]]:
    """Generate segment and total ranges from durations."""
    if not durations:
        return [], [{"start": 0, "end": 0}]

    segments = []
    cumulative = 0
    for d in durations:
        segments.append({"start": cumulative, "end": cumulative + d})
        cumulative += d

    return segments, [{"start": 0, "end": cumulative}]


def _cleanup_temp_files(temp_files: List[str]) -> None:
    """Safely remove temporary audio files."""
    for path in temp_files:
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except Exception as e:
                logger.warning(f"Failed to cleanup {path}: {e}")
