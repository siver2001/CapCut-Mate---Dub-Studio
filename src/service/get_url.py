from src.utils.logger import logger
from exceptions import CustomException, CustomError

def get_url(output: str) -> str:
    """
    Extract linkBusiness logic


    Args:
    output: extracted content


    Returns:
    str: extraction result


    Raises:
    CustomException: ExtractFailed
"""
    logger.info(f'get_url starting, output: {output}')
    try:
        result = output
        logger.info(f'get_url completed successfully, result: {result}')
        return result
    except Exception as e:
        logger.error(f'get_url failed: {str(e)}')
        raise CustomException(CustomError.UNKNOWN_ERROR)