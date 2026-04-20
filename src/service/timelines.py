import random
from src.utils.logger import logger
from typing import List, Dict, Tuple

def timelines(duration: int, num: int, start: int, type: int) -> Tuple[List[Dict[str, int]], List[Dict[str, int]]]:
    """
    Calculate timeline split points for a given duration.
    
    Args:
        duration: Total duration (microseconds).
        num: Number of segments to split into.
        start: Initial start time offset.
        type: Split type (0: Uniform, 1: Random).
        
    Returns:
        tuple: (list of segment timelines, list containing the total timeline range)
    """
    logger.info(f"timelines: duration={duration}, num={num}, start={start}, type={type}")
    
    timelines_list = []
    all_timelines = [{"start": start, "end": start + duration}]
    
    if num <= 0:
        return ([], all_timelines)

    if type == 0:
        # Uniform split
        segment_duration = duration // num
        for i in range(num):
            seg_start = start + i * segment_duration
            if i == num - 1:
                seg_end = start + duration
            else:
                seg_end = start + (i + 1) * segment_duration
            timelines_list.append({"start": seg_start, "end": seg_end})
    else:
        # Random split
        random.seed(42)
        points = sorted([random.randint(start, start + duration) for _ in range(num - 1)])
        points = [start] + points + [start + duration]
        for i in range(len(points) - 1):
            timelines_list.append({"start": points[i], "end": points[i + 1]})
            
    return (timelines_list, all_timelines)