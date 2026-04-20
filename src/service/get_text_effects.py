"""
Logic for retrieving text effect (stylized text) lists.
"""
from typing import List, Dict, Any
from src.utils.logger import logger
from exceptions import CustomException, CustomError
from src.pyJianYingDraft.metadata import TextEffectType

def get_text_effects(mode: int = 0) -> List[Dict[str, Any]]:
    """
    Retrieve list of text effects.
    
    Args:
        mode: 0=All, 1=VIP, 2=Free.
    """
    logger.info(f"get_text_effects called with mode: {mode}")

    try:
        if mode not in [0, 1, 2]:
            raise CustomException(CustomError.EFFECT_GET_FAILED)

        all_effects = []
        for te in TextEffectType:
            all_effects.append({
                "name": te.value.name,
                "is_vip": te.value.is_vip,
                "resource_id": te.value.resource_id,
                "effect_id": te.value.effect_id
            })

        if mode == 1:
            return [e for e in all_effects if e["is_vip"]]
        elif mode == 2:
            return [e for e in all_effects if not e["is_vip"]]
        return all_effects

    except CustomException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_text_effects: {str(e)}")
        raise CustomException(CustomError.EFFECT_GET_FAILED)
