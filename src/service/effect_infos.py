from src.utils.logger import logger
import json
from typing import List, Dict

def effect_infos(effects: List[str], timelines: List[Dict[str, int]]) -> str:
    """
    Generate an effect info JSON string from effect names and timelines.
    
    Args:
        effects: List of effect names.
        timelines: List of timeline dictionaries.
        
    Returns:
        str: JSON string containing processed effect information.
    """
    logger.info(f"effect_infos: processing {len(effects)} effects and {len(timelines)} timelines")
    
    count = min(len(effects), len(timelines))
    if len(effects) != len(timelines):
        logger.warning(f"Length mismatch: effects({len(effects)}) vs timelines({len(timelines)}). Using {count}.")

    result = []
    for i in range(count):
        result.append({
            "name": effects[i], 
            "start": timelines[i]["start"], 
            "duration": timelines[i]["duration"]
        })
    
    return json.dumps(result, ensure_ascii=False)