from typing import List, Tuple, Optional
import asyncio
from src.utils.logger import logger
from src.pyJianYingDraft import ScriptFile, MaskType
from src.pyJianYingDraft.video_segment import VideoSegment
from src.pyJianYingDraft.segment import VisualSegment
from src.utils.draft_cache import DRAFT_CACHE
from exceptions import CustomException, CustomError
from src.utils import helper
from src.utils.draft_lock_manager import DraftLockManager


def add_masks(
    draft_url: str,
    segment_ids: List[str],
    name: str = "Line",
    X: int = 0,
    Y: int = 0,
    width: int = 512,
    height: int = 512,
    feather: int = 0,
    rotation: int = 0,
    invert: bool = False,
    roundCorner: int = 0
) -> Tuple[str, int, List[str], List[str]]:
    """
    Business logic for adding mask effects to specified segments in an existing draft.

    Args:
        draft_url: Draft URL, required.
        segment_ids: Array of segment IDs to apply the mask to, required.
        name: Mask type name, default: "Line".
        X: Mask center X coordinate (pixels).
        Y: Mask center Y coordinate (pixels).
        width: Mask width (pixels).
        height: Mask height (pixels).
        feather: Feathering degree (0-100).
        rotation: Rotation angle (degrees).
        invert: Whether to invert the mask.
        roundCorner: Rounded corner radius (0-100).

    Returns:
        tuple: (draft_url, masks_added, affected_segments, mask_ids)
    """
    logger.info(f"add_masks started, draft_url: {draft_url}, segment_ids: {segment_ids}, mask_name: {name}")

    draft_id = helper.get_url_param(draft_url, "draft_id")
    if not draft_id or draft_id not in DRAFT_CACHE:
        logger.error(f"Invalid draft_url or draft not found in cache: {draft_url}")
        raise CustomException(CustomError.INVALID_DRAFT_URL)

    if not segment_ids:
        logger.error("No segment_ids provided")
        raise CustomException(CustomError.INVALID_MASK_INFO)

    script: ScriptFile = DRAFT_CACHE[draft_id]
    mask_type = find_mask_type_by_name(name)
    if mask_type is None:
        logger.error(f"Mask type not found for name: {name}")
        raise CustomException(CustomError.MASK_NOT_FOUND)

    masks_added = 0
    affected_segments: List[str] = []
    mask_ids: List[str] = []

    for segment_id in segment_ids:
        try:
            mask_id = add_mask_to_segment(
                script=script,
                segment_id=segment_id,
                mask_type=mask_type,
                center_x=X,
                center_y=Y,
                width=width,
                height=height,
                feather=feather,
                rotation=rotation,
                invert=invert,
                round_corner=roundCorner
            )
            masks_added += 1
            affected_segments.append(segment_id)
            mask_ids.append(mask_id)
        except Exception as e:
            logger.error(f"Failed to add mask to segment {segment_id}: {str(e)}")
            # We continue processing other segments even if one fails

    script.save()
    logger.info(f"add_masks completed: {masks_added} masks added to {draft_id}")
    return draft_url, masks_added, affected_segments, mask_ids


async def add_masks_async(
    draft_url: str,
    segment_ids: List[str],
    name: str = "Line",
    X: int = 0,
    Y: int = 0,
    width: int = 512,
    height: int = 512,
    feather: int = 0,
    rotation: int = 0,
    invert: bool = False,
    roundCorner: int = 0,
    lock_timeout: float = 30.0
) -> Tuple[str, int, List[str], List[str]]:
    """Async version of add_masks with draft lock protection."""
    draft_id = helper.get_url_param(draft_url, "draft_id")
    if not draft_id:
        raise CustomException(CustomError.INVALID_DRAFT_URL)

    lock_manager = DraftLockManager()
    try:
        await lock_manager.acquire_lock(draft_id, timeout=lock_timeout)
        return add_masks(
            draft_url=draft_url,
            segment_ids=segment_ids,
            name=name,
            X=X,
            Y=Y,
            width=width,
            height=height,
            feather=feather,
            rotation=rotation,
            invert=invert,
            roundCorner=roundCorner
        )
    except asyncio.TimeoutError:
        logger.error(f"Timeout acquiring lock for draft {draft_id}")
        raise CustomException(CustomError.DRAFT_LOCK_TIMEOUT)
    finally:
        await lock_manager.release_lock(draft_id)


def add_mask_to_segment(
    script: ScriptFile,
    segment_id: str,
    mask_type: MaskType,
    center_x: int = 0,
    center_y: int = 0,
    width: int = 512,
    height: int = 512,
    feather: int = 0,
    rotation: int = 0,
    invert: bool = False,
    round_corner: int = 0
) -> str:
    """Add a mask to a specific visual segment."""
    segment = find_segment_by_id(script, segment_id)
    if not segment:
        raise CustomException(CustomError.SEGMENT_NOT_FOUND)

    if not isinstance(segment, VideoSegment):
        logger.error(f"Segment {segment_id} is not a VideoSegment, cannot add mask")
        raise CustomException(CustomError.INVALID_SEGMENT_TYPE)

    if segment.mask is not None:
        return segment.mask.global_id

    material_width, material_height = segment.material_size
    size, rect_width = calculate_mask_size_params(
        mask_type=mask_type,
        width=width,
        height=height,
        material_width=material_width,
        material_height=material_height
    )

    if mask_type == MaskType.Rectangle:
        segment.add_mask(
            mask_type=mask_type,
            center_x=float(center_x),
            center_y=float(center_y),
            size=size,
            rotation=float(rotation),
            feather=float(feather),
            invert=invert,
            rect_width=rect_width,
            round_corner=float(round_corner)
        )
    else:
        segment.add_mask(
            mask_type=mask_type,
            center_x=float(center_x),
            center_y=float(center_y),
            size=size,
            rotation=float(rotation),
            feather=float(feather),
            invert=invert
        )

    if segment.mask:
        # Register mask to materials
        mask_json = segment.mask.export_json()
        if not any(m.get("id") == mask_json["id"] for m in script.materials.masks):
            script.materials.masks.append(mask_json)
        return segment.mask.global_id
    
    raise CustomException(CustomError.MASK_ADD_FAILED)


def find_segment_by_id(script: ScriptFile, segment_id: str) -> Optional[VisualSegment]:
    """Search for a segment by ID in all tracks."""
    for track in script.tracks.values():
        for segment in track.segments:
            if segment.segment_id == segment_id:
                return segment
    return None


def calculate_mask_size_params(
    mask_type: MaskType,
    width: int,
    height: int,
    material_width: int,
    material_height: int
) -> Tuple[float, Optional[float]]:
    """Calculate mask size ratios relative to material dimensions."""
    size = height / material_height
    rect_width = width / material_width if mask_type == MaskType.Rectangle else None
    return size, rect_width


def find_mask_type_by_name(mask_name: str) -> Optional[MaskType]:
    """Map string mask name to MaskType enum."""
    for mt in MaskType:
        if mt.value.name.lower() == mask_name.lower():
            return mt
    return None
