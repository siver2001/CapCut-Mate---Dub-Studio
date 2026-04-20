"""
Logic for retrieving image animation lists.
"""
from typing import List, Dict, Any
from src.utils.logger import logger
from exceptions import CustomException, CustomError
from src.pyJianYingDraft.metadata import ImageAnimationType

def get_image_animations(mode: int = 0) -> List[Dict[str, Any]]:
    """
    Retrieve list of image animations.
    
    Args:
        mode: 0=All, 1=VIP, 2=Free.
    """
    logger.info(f"get_image_animations called with mode: {mode}")

    try:
        if mode not in [0, 1, 2]:
            raise CustomException(CustomError.ANIMATION_GET_FAILED)

        all_anims = []
        for at in ImageAnimationType:
            all_anims.append({
                "name": at.value.name,
                "is_vip": at.value.is_vip,
                "resource_id": at.value.resource_id,
                "anim_id": at.value.anim_id,
                "type": at.value.type.name # in, out, or combo
            })

        if mode == 1:
            return [a for a in all_anims if a["is_vip"]]
        elif mode == 2:
            return [a for a in all_anims if not a["is_vip"]]
        return all_anims

    except CustomException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_image_animations: {str(e)}")
        raise CustomException(CustomError.ANIMATION_GET_FAILED)
