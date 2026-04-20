from src.utils.logger import logger
import json
from typing import List, Dict, Optional

def filter_infos(
    filters: List[str], 
    timelines: List[Dict[str, int]], 
    intensities: Optional[List[float]] = None
) -> str:
    """
    Generate a filter info JSON string from filter names, timelines, and intensities.
    """
    logger.info(f"filter_infos: processing {len(filters)} filters and {len(timelines)} timelines")
    
    min_len = min(len(filters), len(timelines))
    if intensities is not None:
        min_len = min(min_len, len(intensities))

    if len(filters) != len(timelines) or (intensities is not None and len(intensities) != min_len):
        logger.warning(f"Length mismatch: filters({len(filters)}), timelines({len(timelines)}), intensities({len(intensities) if intensities else 'N/A'}). Using {min_len}.")

    filters = filters[:min_len]
    timelines = timelines[:min_len]
    if intensities is not None:
        intensities = intensities[:min_len]

    infos = []
    for i in range(min_len):
        intensity = intensities[i] if intensities is not None else 100.0
        info = {
            "filter_title": filters[i], 
            "start": timelines[i]["start"], 
            "end": timelines[i]["end"], 
            "intensity": intensity
        }
        infos.append(info)
        logger.info(f"Processed filter info {i + 1}: {info}")

    infos_json = json.dumps(infos, ensure_ascii=False)
    logger.info(f"Generated JSON with {len(infos)} items")
    return infos_json