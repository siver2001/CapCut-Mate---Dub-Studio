from src.utils.logger import logger
import json
from typing import List, Optional, Dict

def audio_infos(
    mp3_urls: List[str], 
    timelines: List[Dict[str, int]], 
    audio_effect: Optional[str] = None, 
    volume: Optional[float] = None
) -> str:
    """
    Generate an audio info JSON string from audio URLs and timelines.
    
    Args:
        mp3_urls: List of audio file URLs.
        timelines: List of timeline dictionaries.
        audio_effect: Optional audio effect name.
        volume: Optional volume level.
        
    Returns:
        str: JSON string containing processed audio information.
    """
    logger.info(f"audio_infos: processing {len(mp3_urls)} URLs and {len(timelines)} timelines")
    
    if len(mp3_urls) != len(timelines):
        min_len = min(len(mp3_urls), len(timelines))
        logger.warning(f"Length mismatch: URLs({len(mp3_urls)}) vs Timelines({len(timelines)}). Using {min_len}.")
        mp3_urls = mp3_urls[:min_len]
        timelines = timelines[:min_len]

    infos = []
    for i, (audio_url, timeline) in enumerate(zip(mp3_urls, timelines)):
        info = {
            "audio_url": audio_url,
            "start": timeline["start"],
            "end": timeline["end"]
        }
        if audio_effect is not None:
            info["audio_effect"] = audio_effect
        if volume is not None:
            info["volume"] = volume
        
        infos.append(info)
        logger.info(f"Processed audio info {i + 1}: {info}")

    infos_json = json.dumps(infos, ensure_ascii=False)
    logger.info(f"Generated JSON with {len(infos)} items")
    return infos_json