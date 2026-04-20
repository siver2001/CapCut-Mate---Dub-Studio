from src.utils.logger import logger
from src.utils.video_task_manager import task_manager
from src.utils.points import get_user_points
from exceptions import CustomException, CustomError
import config


def gen_video(draft_url: str, apiKey: str = None) -> str:
    """
    Submit video generation task (Async Process).

    Args:
        draft_url: Draft URL
        apiKey: Optional API Key for billing

    Returns:
        message: Success message
    """
    logger.info(f"gen_video called with draft_url: {draft_url}")

    try:
        if config.ENABLE_APIKEY:
            if not apiKey:
                raise CustomException(CustomError.INVALID_APIKEY)

            user_points = get_user_points(apiKey)
            if user_points <= 1:
                logger.error(f"Insufficient balance: {user_points} for API key: {apiKey[:8]}***")
                raise CustomException(CustomError.INSUFFICIENT_ACCOUNT_BALANCE)

        validate_draft_url(draft_url)

        # Submit Task to queue
        task_manager.submit_task(draft_url, apiKey)

        logger.info(f"Video generation task submitted for draft_url: {draft_url}")
        return "Video generation task submitted, please use draft_url to query progress"

    except CustomException:
        raise
    except ValueError as e:
        logger.error(f"Invalid draft_url: {draft_url}, error: {e}")
        raise CustomException(CustomError.INVALID_DRAFT_URL)
    except Exception as e:
        logger.error(f"Submit video generation task failed: {e}")
        raise CustomException(CustomError.INTERNAL_SERVER_ERROR)


def validate_draft_url(draft_url: str) -> None:
    """Basic validation for the draft URL structure."""
    if not draft_url or "draft_id=" not in draft_url:
        raise ValueError("Draft URL must contain draft_id parameter")
