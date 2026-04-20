"""
Logic for retrieving video effect lists.
"""
from typing import List, Dict, Any
from src.utils.logger import logger
from exceptions import CustomException, CustomError
from src.pyJianYingDraft.metadata.video_scene_effect import VideoSceneEffectType

def get_effects(mode: int = 0) -> List[Dict[str, Any]]:
    """
    Retrieve list of video effects.
    
    Args:
        mode: 0=All, 1=VIP, 2=Free.
    """
    logger.info(f"get_effects called with mode: {mode}")

    try:
        if mode not in [0, 1, 2]:
            raise CustomException(CustomError.EFFECT_GET_FAILED)

        all_effects = []
        for et in VideoSceneEffectType:
            all_effects.append({
                "name": et.value.name,
                "is_vip": et.value.is_vip,
                "resource_id": et.value.resource_id,
                "effect_id": et.value.effect_id,
                "icon_url": "",
                "has_params": len(et.value.params) > 0
            })

        if mode == 1:
            return [e for e in all_effects if e["is_vip"]]
        elif mode == 2:
            return [e for e in all_effects if not e["is_vip"]]
        return all_effects

    except CustomException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_effects: {str(e)}")
        raise CustomException(CustomError.EFFECT_GET_FAILED)
