import os
import json
import asyncio
import time
from typing import List, Dict, Any, Tuple, Optional
from src.utils.logger import logger
from src.pyJianYingDraft import ScriptFile, trange, AudioSceneEffectType, VideoSceneEffectType, VideoCharacterEffectType
import src.pyJianYingDraft as draft
from src.pyJianYingDraft.local_materials import AudioMaterial
from src.utils.draft_cache import DRAFT_CACHE
from exceptions import CustomException, CustomError
from src.utils import helper
from src.utils.download import download
import config
from src.utils.draft_lock_manager import DraftLockManager


def add_audios(
    draft_url: str,
    audio_infos: str
) -> Tuple[str, str, List[str]]:
    """
    Business logic for adding audios to CapCut draft (Synchronous version).
    """
    return _add_audios_internal(draft_url, audio_infos, prepared_audios=None)


async def add_audios_async(
    draft_url: str,
    audio_infos: str,
    lock_timeout: float = 30.0
) -> Tuple[str, str, List[str]]:
    """
    Add audios to CapCut draft (Async version with lock protection).
    """
    draft_id = helper.get_url_param(draft_url, "draft_id")
    if not draft_id:
        raise CustomException(CustomError.INVALID_DRAFT_URL)

    # Download materials first
    prepared_audios = await asyncio.to_thread(
        _prepare_audios_local_files,
        draft_url,
        audio_infos
    )

    lock_manager = DraftLockManager()
    try:
        await lock_manager.acquire_lock(draft_id, timeout=lock_timeout)
        return _add_audios_internal(draft_url, audio_infos, prepared_audios=prepared_audios)
    except asyncio.TimeoutError:
        logger.error(f"Timeout acquiring lock for draft {draft_id}")
        raise CustomException(CustomError.DRAFT_LOCK_TIMEOUT)
    finally:
        await lock_manager.release_lock(draft_id)


def _prepare_audios_local_files(draft_url: str, audio_infos: str) -> List[Dict[str, Any]]:
    """Download audio materials without modifying the script."""
    draft_id = validate_and_get_draft_id(draft_url)
    draft_dir = os.path.join(config.DRAFT_DIR, draft_id)
    draft_audio_dir = os.path.join(draft_dir, "assets", "audios")
    os.makedirs(draft_audio_dir, exist_ok=True)

    audios = parse_audio_data(audio_infos)
    for audio in audios:
        audio["local_audio_path"] = download(url=audio['audio_url'], save_dir=draft_audio_dir)
    
    return audios


def _add_audios_internal(
    draft_url: str,
    audio_infos: str,
    prepared_audios: Optional[List[Dict[str, Any]]] = None
) -> Tuple[str, str, List[str]]:
    """Internal logic for adding audios to a draft."""
    draft_id = validate_and_get_draft_id(draft_url)
    script: ScriptFile = DRAFT_CACHE[draft_id]

    if prepared_audios is not None:
        audios = prepared_audios
    else:
        audios = _prepare_audios_local_files(draft_url, audio_infos)

    track_name = f"audio_track_{helper.gen_unique_id()}"
    script.add_track(track_type=draft.TrackType.audio, track_name=track_name, relative_index=10)

    draft_dir = os.path.join(config.DRAFT_DIR, draft_id)
    draft_audio_dir = os.path.join(draft_dir, "assets", "audios")

    audio_ids = []
    for audio in audios:
        audio_id = add_audio_to_draft(script, track_name, draft_audio_dir, audio)
        audio_ids.append(audio_id)

    script.save()
    
    track_id = ""
    for track in script.tracks.values():
        if track.name == track_name:
            track_id = track.track_id
            break

    return draft_url, track_id, audio_ids


def add_audio_to_draft(
    script: ScriptFile,
    track_name: str,
    draft_audio_dir: str,
    audio: dict
) -> str:
    """Add a single audio segment to a specific track."""
    audio_path = audio.get("local_audio_path")
    if not audio_path:
        audio_path = download(url=audio['audio_url'], save_dir=draft_audio_dir)

    temp_material = AudioMaterial(audio_path)
    actual_duration = temp_material.duration
    
    start_time = max(0, audio['start'])
    requested_duration = audio['end'] - audio['start']
    segment_duration = min(requested_duration, actual_duration)
    
    audio_segment = draft.AudioSegment(
        material=audio_path,
        target_timerange=trange(start=start_time, duration=segment_duration),
        volume=audio['volume']
    )

    if audio.get('audio_effect'):
        add_audio_effect(audio_segment, audio['audio_effect'])

    script.add_segment(audio_segment, track_name)
    return audio_segment.material_instance.material_id


def add_audio_effect(audio_segment, audio_effect: str):
    """Apply an audio effect to a segment."""
    effect_type = find_audio_effect_type(audio_effect)
    if effect_type:
        # Simplified parameter mapping
        params_list = []
        for param in effect_type.value.params:
            if param.min_value != param.max_value:
                val = ((param.default_value - param.min_value) / (param.max_value - param.min_value)) * 100
            else:
                val = 50
            params_list.append(val)
        
        audio_segment.add_effect(effect_type=effect_type, params=params_list)
        logger.info(f"Added effect {audio_effect} to segment")


def find_audio_effect_type(audio_effect: str):
    """Find effect type by name in various effect categories."""
    for category in [AudioSceneEffectType, VideoSceneEffectType, VideoCharacterEffectType]:
        for effect_meta in category.__members__.values():
            if effect_meta.value.name.lower() == audio_effect.lower():
                return effect_meta
    return None


def validate_and_get_draft_id(draft_url: str) -> str:
    """Validate URL and retrieve draft ID from cache."""
    draft_id = helper.get_url_param(draft_url, "draft_id")
    if not draft_id or draft_id not in DRAFT_CACHE:
        raise CustomException(CustomError.INVALID_DRAFT_URL)
    return draft_id


def parse_audio_data(json_str: str) -> List[Dict[str, Any]]:
    """Parse audio metadata from JSON string."""
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise CustomException(CustomError.INVALID_AUDIO_INFO, f"JSON parse error: {e.msg}")

    if not isinstance(data, list):
        raise CustomException(CustomError.INVALID_AUDIO_INFO, "audio_infos must be a list")

    result = []
    for item in data:
        if all(k in item for k in ["audio_url", "start", "end"]):
            result.append({
                "audio_url": item["audio_url"],
                "start": item["start"],
                "end": item["end"],
                "volume": max(0.0, min(2.0, item.get("volume", 1.0))),
                "audio_effect": item.get("audio_effect")
            })
    return result
