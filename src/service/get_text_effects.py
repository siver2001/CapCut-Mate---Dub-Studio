"""
Logic for retrieving text effect (stylized text) lists.
"""
import json
import os
from typing import List, Dict, Any, Optional
from src.utils.logger import logger
from exceptions import CustomException, CustomError
from config import HUAZI_CONFIG_PATH

_TEXT_EFFECTS_CACHE = []

def _load_text_effects():
    global _TEXT_EFFECTS_CACHE
    if not _TEXT_EFFECTS_CACHE:
        try:
            with open(HUAZI_CONFIG_PATH, "r", encoding="utf-8") as f:
                _TEXT_EFFECTS_CACHE = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load huazi.json: {e}")
            _TEXT_EFFECTS_CACHE = []
    return _TEXT_EFFECTS_CACHE

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

        all_effects = _load_text_effects()

        # Format to match expected output if needed, or just return directly
        formatted = []
        for te in all_effects:
            formatted.append({
                "name": te.get("title", ""),
                "is_vip": te.get("is_vip", False),
                "resource_id": te.get("id", ""),
                "effect_id": te.get("id", "")
            })

        if mode == 1:
            return [e for e in formatted if e["is_vip"]]
        elif mode == 2:
            return [e for e in formatted if not e["is_vip"]]
        return formatted

    except CustomException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_text_effects: {str(e)}")
        raise CustomException(CustomError.EFFECT_GET_FAILED)

def resolve_text_effect(effect_id_or_name: str) -> Optional[Dict[str, Any]]:
    """Resolve a text effect by ID or name."""
    effects = get_text_effects(mode=0)
    for eff in effects:
        if eff["effect_id"] == effect_id_or_name or eff["name"] == effect_id_or_name:
            return eff
    return None
