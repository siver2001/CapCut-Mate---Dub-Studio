from src.utils.logger import logger
import json
from typing import List, Optional, Dict, Any

def caption_infos(
    texts: List[str], 
    timelines: List[Dict[str, int]], 
    font_size: Optional[int] = None, 
    keyword_color: Optional[str] = None, 
    keyword_border_color: Optional[str] = None, 
    keyword_font_size: Optional[int] = None, 
    keywords: Optional[List[str]] = None, 
    in_animation: Optional[str] = None, 
    in_animation_duration: Optional[int] = None, 
    loop_animation: Optional[str] = None, 
    loop_animation_duration: Optional[int] = None, 
    out_animation: Optional[str] = None, 
    out_animation_duration: Optional[int] = None, 
    transition: Optional[str] = None, 
    transition_duration: Optional[int] = None
) -> str:
    """
    Generate a caption info JSON string from texts and timelines.
    """
    logger.info(f"caption_infos: processing {len(texts)} texts and {len(timelines)} timelines")
    
    if len(texts) != len(timelines):
        min_len = min(len(texts), len(timelines))
        logger.warning(f"Length mismatch: texts({len(texts)}) vs timelines({len(timelines)}). Using {min_len}.")
        texts = texts[:min_len]
        timelines = timelines[:min_len]

    infos = []
    for i, (text, timeline) in enumerate(zip(texts, timelines)):
        info = _build_caption_info(
            text, timeline, i, keywords, font_size, 
            keyword_color, keyword_border_color, keyword_font_size, 
            in_animation, in_animation_duration, 
            loop_animation, loop_animation_duration, 
            out_animation, out_animation_duration, 
            transition, transition_duration
        )
        infos.append(info)
        logger.info(f"Processed caption info {i + 1}")

    infos_json = json.dumps(infos, ensure_ascii=False)
    return infos_json

def _build_caption_info(
    text: str, 
    timeline: Dict[str, int], 
    index: int, 
    keywords: Optional[List[str]], 
    font_size: Optional[int], 
    keyword_color: Optional[str], 
    keyword_border_color: Optional[str], 
    keyword_font_size: Optional[int], 
    in_animation: Optional[str], 
    in_animation_duration: Optional[int], 
    loop_animation: Optional[str], 
    loop_animation_duration: Optional[int], 
    out_animation: Optional[str], 
    out_animation_duration: Optional[int], 
    transition: Optional[str], 
    transition_duration: Optional[int]
) -> Dict[str, Any]:
    """Build a single caption info dictionary."""
    info = {
        "start": timeline["start"],
        "end": timeline["end"],
        "text": text
    }
    
    if keywords and index < len(keywords):
        info["keyword"] = keywords[index]
    elif keywords:
        info["keyword"] = ""

    if keyword_color is not None: info["keyword_color"] = keyword_color
    if keyword_border_color is not None: info["keyword_border_color"] = keyword_border_color
    if keyword_font_size is not None: info["keyword_font_size"] = keyword_font_size
    if font_size is not None: info["font_size"] = font_size
    
    if in_animation is not None: info["in_animation"] = in_animation
    if in_animation_duration is not None: info["in_animation_duration"] = in_animation_duration
    if loop_animation is not None: info["loop_animation"] = loop_animation
    if loop_animation_duration is not None: info["loop_animation_duration"] = loop_animation_duration
    if out_animation is not None: info["out_animation"] = out_animation
    if out_animation_duration is not None: info["out_animation_duration"] = out_animation_duration
    if transition is not None: info["transition"] = transition
    if transition_duration is not None: info["transition_duration"] = transition_duration
    
    return info