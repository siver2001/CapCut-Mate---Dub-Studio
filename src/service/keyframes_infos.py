from src.utils.logger import logger
import json
from typing import List, Dict, Any

def calculate_relative_time_offset(offset_percent: int, duration: int) -> int:
    """Calculate relative time offset from percentage and duration."""
    return int(offset_percent / 100.0 * duration)

def normalize_keyframe_value(ctype: str, value: float, height: int = None, width: int = None) -> float:
    """Normalize keyframe value based on its type and video dimensions."""
    normalized_value = value
    if ctype == "KFTypePositionX" and width is not None and width > 0:
        normalized_value = value / width
    elif ctype == "KFTypePositionY" and height is not None and height > 0:
        normalized_value = value / height
    return normalized_value

def keyframes_infos(
    ctype: str, 
    offsets: str, 
    values: str, 
    segment_infos: List[Dict[str, Any]], 
    height: int = None, 
    width: int = None
) -> str:
    """
    Generate a keyframe info JSON string from offsets and values for given segments.
    """
    logger.info(f"keyframes_infos: ctype={ctype}, offsets={offsets}, values={values}")
    
    offset_list = [int(x) for x in offsets.split("|")]
    value_list = [float(x) for x in values.split("|")]
    
    if len(offset_list) != len(value_list):
        raise ValueError(f"Length mismatch: offsets({len(offset_list)}) vs values({len(value_list)})")

    keyframes = []
    for segment_info in segment_infos:
        segment_id = segment_info["id"]
        duration = segment_info["end"] - segment_info["start"]
        
        for offset_percent, value in zip(offset_list, value_list):
            relative_time_offset = calculate_relative_time_offset(offset_percent, duration)
            normalized_value = normalize_keyframe_value(ctype, value, height, width)
            
            keyframe = {
                "offset": relative_time_offset,
                "property": ctype,
                "segment_id": segment_id,
                "value": normalized_value
            }
            keyframes.append(keyframe)
            logger.info(f"Added keyframe: {keyframe}")

    result_json = json.dumps(keyframes, ensure_ascii=False)
    logger.info(f"Generated JSON with {len(keyframes)} items")
    return result_json