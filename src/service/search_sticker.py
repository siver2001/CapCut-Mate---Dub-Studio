import json
import random
import os
from typing import List, Dict, Any
from src.utils.logger import logger
import config

def search_sticker(keyword: str) -> List[Dict[str, Any]]:
    """
    Search for stickers by keyword.
    
    Args:
        keyword: Search term.
        
    Returns:
        List[Dict[str, Any]]: Up to 50 sticker records.
    """
    logger.info(f"search_sticker called for keyword: {keyword}")

    try:
        if not os.path.exists(config.STICKER_CONFIG_PATH):
            logger.error(f"Sticker config not found: {config.STICKER_CONFIG_PATH}")
            return []

        with open(config.STICKER_CONFIG_PATH, 'r', encoding='utf-8') as f:
            all_stickers = json.load(f)

        # Simple keyword matching
        matches = [s for s in all_stickers if keyword.lower() in s.get("title", "").lower()]
        
        # Fallback to random if no matches
        if not matches:
            logger.info("No matches, returning random stickers")
            return random.sample(all_stickers, min(50, len(all_stickers)))

        return matches[:50]
    except Exception as e:
        logger.error(f"Failed to search stickers: {str(e)}")
        return []
