import json
from typing import List, Dict, Any
import urllib.request
import urllib.error
from src.utils.logger import logger

CAPCUT_MATE_API = "https://capcut-mate.jcaigc.cn"


def search_sticker(keyword: str) -> List[Dict[str, Any]]:
    """
    Search for stickers by keyword using CapCut Mate cloud API.

    Args:
        keyword: Search term.

    Returns:
        List[Dict[str, Any]]: Up to 50 sticker records.
    """
    logger.info(f"search_sticker called for keyword: {keyword}")

    url = f"{CAPCUT_MATE_API}/openapi/capcut-mate/v1/search_sticker"
    payload = json.dumps({"keyword": keyword}).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
    }

    try:
        req = urllib.request.Request(
            url=url,
            data=payload,
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode("utf-8"))

        code = result.get("code", 0)
        if code != 0:
            logger.error(f"CapCut Mate API error: {result.get('message', 'unknown')}")
            return []

        raw_data = result.get("data", [])
        stickers: List[Dict[str, Any]] = []
        for item in raw_data[:50]:
            sticker_info = item.get("sticker", {})
            sticker_id = str(item.get("sticker_id", ""))
            title = str(item.get("title", ""))
            large_image = sticker_info.get("large_image", {})
            image_url = str(large_image.get("image_url", ""))
            package = sticker_info.get("sticker_package", {})
            stickers.append({
                "sticker_id": sticker_id,
                "title": title,
                "image_url": image_url,
                "width": package.get("width_per_frame", 0),
                "height": package.get("height_per_frame", 0),
                "size": package.get("size", 0),
                "sticker_type": sticker_info.get("sticker_type", 1),
            })

        logger.info(f"search_sticker returned {len(stickers)} stickers for '{keyword}'")
        return stickers

    except urllib.error.HTTPError as e:
        logger.error(f"HTTP error {e.code} calling CapCut Mate search_sticker: {e.read().decode()}")
        return []
    except Exception as e:
        logger.error(f"Failed to search stickers from cloud API: {e}")
        return []
