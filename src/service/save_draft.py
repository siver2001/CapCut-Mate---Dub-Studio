import os
import asyncio
from src.utils.logger import logger
from src.utils.draft_cache import DRAFT_CACHE
from src.utils import helper
from exceptions import CustomException, CustomError
import config
from src.utils.draft_lock_manager import DraftLockManager

def save_draft(draft_url: str) -> str:
    """
    Save the CapCut draft based on the draft URL.
    """
    draft_id = helper.get_url_param(draft_url, "draft_id")
    if not draft_id or draft_id not in DRAFT_CACHE:
        logger.info("Invalid draft URL: %s", draft_url)
        raise CustomException(CustomError.INVALID_DRAFT_URL)

    script = DRAFT_CACHE[draft_id]
    script.save()
    logger.info("Draft saved successfully: %s", os.path.join(config.DRAFT_DIR, draft_id))
    return draft_url

async def save_draft_async(draft_url: str, lock_timeout: float = 30.0) -> str:
    """
    Save the CapCut draft asynchronously with lock protection.
    """
    draft_id = helper.get_url_param(draft_url, "draft_id")
    if not draft_id:
        raise CustomException(CustomError.INVALID_DRAFT_URL)

    lock_manager = DraftLockManager()
    try:
        await lock_manager.acquire_lock(draft_id, timeout=lock_timeout)
        logger.info(f"Lock acquired for draft_id: {draft_id}")
        return save_draft(draft_url)
    except asyncio.TimeoutError:
        logger.error(f"Timeout waiting for lock on draft_id: {draft_id}")
        raise CustomException(CustomError.DRAFT_LOCK_TIMEOUT)
    finally:
        await lock_manager.release_lock(draft_id)
        logger.info(f"Lock released for draft_id: {draft_id}")