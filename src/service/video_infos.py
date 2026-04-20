from src.utils.logger import logger
import json
from typing import List, Optional, Dict, Any

def video_infos(
    video_urls: List[str], 
    timelines: List[Dict[str, int]], 
    height: Optional[int] = None, 
    width: Optional[int] = None, 
    mask: Optional[str] = None, 
    transition: Optional[str] = None, 
    transition_duration: Optional[int] = None, 
    volume: float = 1.0
) -> str:
    """
    Generate a video info JSON string from video URLs and timelines.
    """
    logger.info(f"video_infos: processing {len(video_urls)} videos and {len(timelines)} timelines")
    
    if len(video_urls) != len(timelines):
        min_len = min(len(video_urls), len(timelines))
        logger.warning(f"Length mismatch: videos({len(video_urls)}) vs timelines({len(timelines)}). Using {min_len}.")
        video_urls = video_urls[:min_len]
        timelines = timelines[:min_len]

    infos = []
    for i, (video_url, timeline) in enumerate(zip(video_urls, timelines)):
        start = timeline["start"]
        end = timeline["end"]
        duration = end - start
        
        info = {
            "video_url": video_url, 
            "start": start, 
            "end": end, 
            "duration": duration,
            "volume": volume
        }
        
        if width is not None: info["width"] = width
        if height is not None: info["height"] = height
        if mask is not None: info["mask"] = mask
        if transition is not None: info["transition"] = transition
        if transition_duration is not None: info["transition_duration"] = transition_duration
        
        infos.append(info)
        logger.info(f"Processed video info {i + 1}: {info}")

    infos_json = json.dumps(infos, ensure_ascii=False)
    logger.info(f"Generated JSON with {len(infos)} items")
    return infos_json