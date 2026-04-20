import json
import asyncio
from typing import List, Dict, Any, Tuple, Optional, Union
from src.utils.logger import logger
from src.pyJianYingDraft import ScriptFile, TrackType, EffectSegment, Timerange
from src.pyJianYingDraft.metadata import VideoSceneEffectType, VideoCharacterEffectType
from src.utils.draft_cache import DRAFT_CACHE
from exceptions import CustomException, CustomError
from src.utils import helper
from src.utils.draft_lock_manager import DraftLockManager


def add_effects(
    draft_url: str,
    effect_infos: str
) -> Tuple[str, str, List[str], List[str]]:
    """
    Business logic for adding effects to CapCut draft (Synchronous version).
    """
    logger.info(f"add_effects started, draft_url: {draft_url}")
    
    draft_id = helper.get_url_param(draft_url, "draft_id")
    if not draft_id or draft_id not in DRAFT_CACHE:
        raise CustomException(CustomError.INVALID_DRAFT_URL)

    effect_items = parse_effects_data(effect_infos)
    if not effect_items:
        raise CustomException(CustomError.INVALID_EFFECT_INFO)

    script: ScriptFile = DRAFT_CACHE[draft_id]
    track_name = f"effect_track_{helper.gen_unique_id()}"
    script.add_track(track_type=TrackType.effect, track_name=track_name)

    segment_ids = []
    effect_ids = []
    for item in effect_items:
        try:
            segment_id, effect_id = add_effect_to_draft(script, track_name, effect=item)
            segment_ids.append(segment_id)
            effect_ids.append(effect_id)
        except Exception as e:
            logger.error(f"Failed to add effect: {str(e)}")

    script.save()
    
    track_id = ""
    for track in script.tracks.values():
        if track.name == track_name:
            track_id = track.track_id
            break

    return draft_url, track_id, effect_ids, segment_ids


async def add_effects_async(
    draft_url: str,
    effect_infos: str,
    lock_timeout: float = 30.0
) -> Tuple[str, str, List[str], List[str]]:
    """Async version of add_effects with draft lock protection."""
    draft_id = helper.get_url_param(draft_url, "draft_id")
    if not draft_id:
        raise CustomException(CustomError.INVALID_DRAFT_URL)

    lock_manager = DraftLockManager()
    try:
        await lock_manager.acquire_lock(draft_id, timeout=lock_timeout)
        return add_effects(draft_url, effect_infos)
    except asyncio.TimeoutError:
        logger.error(f"Timeout acquiring lock for draft {draft_id}")
        raise CustomException(CustomError.DRAFT_LOCK_TIMEOUT)
    finally:
        await lock_manager.release_lock(draft_id)


def add_effect_to_draft(
    script: ScriptFile,
    track_name: str,
    effect: dict
) -> Tuple[str, str]:
    """Add a single effect segment to a track."""
    effect_type = find_effect_type_by_name(effect['effect_title'])
    if not effect_type:
        raise CustomException(CustomError.EFFECT_NOT_FOUND)

    timerange = Timerange(start=effect['start'], duration=effect['end'] - effect['start'])
    effect_segment = EffectSegment(effect_type=effect_type, target_timerange=timerange)
    
    script.add_segment(effect_segment, track_name)
    return effect_segment.segment_id, effect_segment.effect_inst.global_id


def find_effect_type_by_name(effect_title: str) -> Optional[Union[VideoSceneEffectType, VideoCharacterEffectType]]:
    """Map effect title to metadata enum."""
    for category in [VideoSceneEffectType, VideoCharacterEffectType]:
        for et in category:
            if et.value.name.lower() == effect_title.lower():
                return et
    return None


def parse_effects_data(json_str: str) -> List[Dict[str, Any]]:
    """Parse and validate effect metadata from JSON string."""
    try:
        data = json.loads(json_str)
        if not isinstance(data, list): return []
        
        result = []
        for item in data:
            if all(k in item for k in ["effect_title", "start", "end"]):
                result.append({
                    "effect_title": str(item["effect_title"]),
                    "start": int(item["start"]),
                    "end": int(item["end"])
                })
        return result
    except:
        return []
