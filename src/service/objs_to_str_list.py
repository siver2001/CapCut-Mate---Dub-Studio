from typing import List, Dict, Any
from src.utils.logger import logger
from exceptions import CustomException, CustomError

def objs_to_str_list(outputs: List[Dict[str, Any]]) -> List[str]:
    """
    Extract string outputs from a list of data objects.
    """
    logger.info(f"objs_to_str_list called for {len(outputs)} items")
    try:
        result = [obj.get("output", "") for obj in outputs]
        return result
    except Exception as e:
        logger.error(f"objs_to_str_list failed: {str(e)}")
        raise CustomException(CustomError.UNKNOWN_ERROR)
