import os
from typing import Optional
from src.utils.logger import logger
from src.utils.download import download
from src.utils.media import get_media_duration
from exceptions import CustomException, CustomError
import config


def get_audio_duration(mp3_url: str) -> int:
    """
    Download an audio file and retrieve its duration in microseconds.
    """
    logger.info(f"get_audio_duration called for URL: {mp3_url}")

    temp_file_path = None
    try:
        temp_file_path = download(mp3_url, config.TEMP_DIR)
        duration_us = get_media_duration(temp_file_path)

        if duration_us is None:
            raise CustomException(CustomError.AUDIO_DURATION_GET_FAILED)

        logger.info(f"Audio duration: {duration_us} microseconds")
        return duration_us

    except CustomException:
        raise
    except Exception as e:
        logger.error(f"Failed to get audio duration: {str(e)}")
        raise CustomException(CustomError.AUDIO_DURATION_GET_FAILED)
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except Exception as e:
                logger.warning(f"Failed to cleanup {temp_file_path}: {e}")
