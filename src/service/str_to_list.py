from src.utils.logger import logger
from exceptions import CustomException, CustomError
from typing import List

def str_to_list(obj: str) -> List[str]:
    """
    String to listBusiness logic


    Args:
    obj: Objectin容（JSONString）


    Returns:
    List[str]: StringList


    Raises:
    CustomException: ConvertFailed
"""
    logger.info(f'str_to_list starting, obj: {obj}')
    try:
        result = [obj]
        logger.info(f'str_to_list completed successfully, result count: {len(result)}')
        return result
    except Exception as e:
        logger.error(f'str_to_list failed: {str(e)}')
        raise CustomException(CustomError.UNKNOWN_ERROR)