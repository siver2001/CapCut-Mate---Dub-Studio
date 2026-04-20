from typing import Dict, Any, Optional
from exceptions import CustomException, CustomError
from src.utils.logger import logger
import requests

# Constants
POINTS_API_BASE_URL = "https://jcaigc.cn/openapi/v1/user/points"
API_HEADERS = {
    'User-Agent': 'CapcutMate/1.0',
    'Accept': 'application/json',
    'Content-Type': 'application/json'
}
DEFAULT_API_TIMEOUT = 30

def get_user_points(api_key: str) -> float:
    """Retrieve current user points using the API key."""
    try:
        params = {'apiKey': api_key}
        result = _call_user_api('GET', '', params=params)
        
        code = result.get('code', -1)
        if code == 0:
            points = result.get('data', {}).get('points', 0.0)
            logger.info(f"Retrieved points: {points} for API key: {api_key[:8]}***")
            return float(points)
        elif code == 10007:
            raise CustomException(CustomError.INVALID_APIKEY)
        else:
            raise CustomException(CustomError.UNKNOWN_ERROR, detail=f"API code: {code}")
            
    except CustomException:
        raise
    except Exception as e:
        logger.error(f"Error getting points: {str(e)}")
        raise CustomException(CustomError.UNKNOWN_ERROR)

def deduct_user_points(api_key: str, points: float, desc: str) -> bool:
    """Deduct points from the user account."""
    try:
        json_data = {
            'apiKey': api_key,
            'points': float(points),
            'desc': desc.strip()
        }
        result = _call_user_api('POST', '/deduct', json_data=json_data)
        
        code = result.get('code', -1)
        if code == 0:
            logger.info(f"Deducted {points} points for {api_key[:8]}***: {desc}")
            return True
        elif code == 10007:
            raise CustomException(CustomError.INVALID_APIKEY)
        return False
    except Exception as e:
        logger.warning(f"Failed to deduct points: {str(e)}")
        return False

def _call_user_api(method: str, endpoint: str, params=None, json_data=None) -> Dict[str, Any]:
    url = f"{POINTS_API_BASE_URL}{endpoint}"
    try:
        if method.upper() == 'GET':
            resp = requests.get(url, params=params, headers=API_HEADERS, timeout=DEFAULT_API_TIMEOUT)
        else:
            resp = requests.post(url, json=json_data, headers=API_HEADERS, timeout=DEFAULT_API_TIMEOUT)
        
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.error(f"User API call failed: {method} {endpoint}, error: {str(e)}")
        raise CustomException(CustomError.INTERNAL_SERVER_ERROR)
