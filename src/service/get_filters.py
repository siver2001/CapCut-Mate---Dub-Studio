"""
Logic for retrieving video filter lists.
"""
from typing import List, Dict, Any
from src.utils.logger import logger
from exceptions import CustomException, CustomError
from src.pyJianYingDraft.metadata import FilterType

def get_filters(mode: int = 0) -> List[Dict[str, Any]]:
    """
    Retrieve list of video filters.
    
    Args:
        mode: 0=All, 1=VIP, 2=Free.
    """
    logger.info(f"get_filters called with mode: {mode}")

    try:
        if mode not in [0, 1, 2]:
            raise CustomException(CustomError.FILTER_GET_FAILED)

        all_filters = []
        for ft in FilterType:
            all_filters.append({
                "name": ft.value.name,
                "is_vip": ft.value.is_vip,
                "resource_id": ft.value.resource_id,
                "filter_id": ft.value.filter_id,
                "icon_url": ""
            })

        if mode == 1:
            return [f for f in all_filters if f["is_vip"]]
        elif mode == 2:
            return [f for f in all_filters if not f["is_vip"]]
        return all_filters

    except CustomException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_filters: {str(e)}")
        raise CustomException(CustomError.FILTER_GET_FAILED)
