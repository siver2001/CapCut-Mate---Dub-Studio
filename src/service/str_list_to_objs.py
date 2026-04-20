from typing import List, Dict, Any
from src.utils.logger import logger
from exceptions import CustomException, CustomError

def str_list_to_objs(infos: List[str]) -> List[Dict[str, Any]]:
    """
    Convert a list of strings into a list of output objects.
    """
    logger.info(f"str_list_to_objs starting for {len(infos)} strings")
    try:
        return [{"output": s} for s in infos]
    except Exception as e:
        logger.error(f"str_list_to_objs failed: {str(e)}")
        raise CustomException(CustomError.UNKNOWN_ERROR)
