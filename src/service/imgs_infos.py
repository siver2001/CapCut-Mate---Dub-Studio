from src.utils.logger import logger
import json
from typing import List, Optional, Dict, Any, Tuple

def imgs_infos(
    imgs: List[str], 
    timelines: List[Dict[str, int]], 
    height: Optional[int] = None, 
    width: Optional[int] = None, 
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
    Generate an image info JSON string from image URLs and timelines.
    """
    logger.info(f"imgs_infos: processing {len(imgs)} images and {len(timelines)} timelines")
    
    if len(imgs) != len(timelines):
        min_len = min(len(imgs), len(timelines))
        logger.warning(f"Length mismatch: imgs({len(imgs)}) vs timelines({len(timelines)}). Using {min_len}.")
        imgs = imgs[:min_len]
        timelines = timelines[:min_len]

    parsed_animations = _parse_animation_params(in_animation, out_animation, loop_animation, transition)
    in_anims, out_anims, loop_anims, trans_anims = parsed_animations
    
    infos = []
    for i, (img_url, timeline) in enumerate(zip(imgs, timelines)):
        info = _build_image_info(
            img_url, timeline, height, width, i, 
            in_anims, out_anims, loop_anims, trans_anims, 
            in_animation_duration, out_animation_duration, 
            loop_animation_duration, transition_duration
        )
        infos.append(info)
        logger.info(f"Processed image info {i + 1}")

    infos_json = json.dumps(infos, ensure_ascii=False)
    logger.info(f"Generated JSON with {len(infos)} items")
    return infos_json

def _parse_animation_params(in_anim, out_anim, loop_anim, trans) -> Tuple[List[str], List[str], List[str], List[str]]:
    """Parse animation strings separated by '|' into lists."""
    def parse_single(param: Optional[str]) -> List[str]:
        if param and isinstance(param, str):
            return [a.strip() for a in param.split("|") if a.strip()]
        return []

    return (
        parse_single(in_anim), 
        parse_single(out_anim), 
        parse_single(loop_anim), 
        parse_single(trans)
    )

def _build_image_info(
    img_url: str, 
    timeline: Dict[str, int], 
    height: Optional[int], 
    width: Optional[int], 
    index: int, 
    in_anims: List[str], 
    out_anims: List[str], 
    loop_anims: List[str], 
    trans_anims: List[str], 
    in_dur: Optional[int], 
    out_dur: Optional[int], 
    loop_dur: Optional[int], 
    trans_dur: Optional[int]
) -> Dict[str, Any]:
    """Build a single image info dictionary."""
    info = {
        "image_url": img_url,
        "start": timeline["start"],
        "end": timeline["end"]
    }
    
    if height is not None: info["height"] = height
    if width is not None: info["width"] = width
    
    _add_animation_with_extension(info, "in_animation", in_anims, index, in_dur)
    _add_animation_with_extension(info, "out_animation", out_anims, index, out_dur)
    _add_animation_with_extension(info, "loop_animation", loop_anims, index, loop_dur)
    _add_animation_with_extension(info, "transition", trans_anims, index, trans_dur)
    
    return info

def _add_animation_with_extension(info, key, animations, index, duration):
    """Add animation with extension logic (reuse last if needed)."""
    if not animations:
        return
        
    if index < len(animations):
        selected = animations[index]
    else:
        selected = animations[-1]
        
    info[key] = selected
    if duration is not None:
        info[f"{key}_duration"] = duration