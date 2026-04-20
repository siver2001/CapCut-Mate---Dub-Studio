import os
import requests
import mimetypes
import time
from typing import Dict, Any, Optional
from src.utils import helper
from src.utils.logger import logger
from exceptions import CustomException, CustomError
import config

# Configuration Constants
DEFAULT_FILE_SIZE_LIMIT = config.DOWNLOAD_FILE_SIZE_LIMIT
DEFAULT_DOWNLOAD_TIMEOUT = 90
DEFAULT_CONNECT_TIMEOUT = 10
DEFAULT_READ_TIMEOUT = 15
DEFAULT_RETRY_COUNT = 3
CHUNK_SIZE = 32768
CHUNK_READ_TIMEOUT = 10
MIN_PARTIAL_SIZE = 1024

DOWNLOAD_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': '*/*',
    'Connection': 'keep-alive'
}

def download(url: str, save_dir: str, limit: int = DEFAULT_FILE_SIZE_LIMIT,
             timeout: int = DEFAULT_DOWNLOAD_TIMEOUT, retry: int = DEFAULT_RETRY_COUNT) -> str:
    """
    Download a file with support for breakpoint resumption and smart retries.
    """
    url = str(url)
    context = _prepare_download_context(url, save_dir, timeout)
    return _execute_download_with_retry(context, limit, retry)

def _prepare_download_context(url: str, save_dir: str, timeout: int) -> dict:
    base_filename = helper.gen_unique_id()
    temp_save_path = os.path.join(save_dir, base_filename)
    
    # Simple check for range support
    supports_range = False
    try:
        resp = requests.head(url, timeout=5, headers=DOWNLOAD_HEADERS)
        supports_range = resp.headers.get('Accept-Ranges') == 'bytes'
    except:
        pass

    return {
        'url': url,
        'save_path': temp_save_path,
        'supports_range': supports_range,
        'timeouts': {
            'connect': DEFAULT_CONNECT_TIMEOUT,
            'read': DEFAULT_READ_TIMEOUT,
            'total': timeout
        }
    }

def _execute_download_with_retry(context: dict, limit: int, retry: int) -> str:
    url = context['url']
    save_path = context['save_path']
    supports_range = context['supports_range']
    
    last_err = None
    for attempt in range(retry + 1):
        try:
            logger.info(f"Download attempt {attempt + 1}/{retry + 1} for {url}")
            
            existing_size = 0
            if os.path.exists(save_path):
                existing_size = os.path.getsize(save_path)
            
            use_resume = supports_range and existing_size > MIN_PARTIAL_SIZE and attempt > 0
            headers = DOWNLOAD_HEADERS.copy()
            if use_resume:
                headers['Range'] = f'bytes={existing_size}-'

            with requests.get(url, headers=headers, stream=True, timeout=(10, 20)) as r:
                r.raise_for_status()
                
                # Determine extension on first successful start
                if existing_size == 0:
                    ext = mimetypes.guess_extension(r.headers.get('Content-Type', '').split(';')[0])
                    if ext:
                        save_path += ext
                        context['save_path'] = save_path

                mode = 'ab' if use_resume else 'wb'
                with open(save_path, mode) as f:
                    for chunk in r.iter_content(chunk_size=CHUNK_SIZE):
                        if chunk:
                            f.write(chunk)
                            if os.path.getsize(save_path) > limit:
                                raise CustomException(CustomError.DOWNLOAD_FILE_TOO_LARGE)

            return save_path
        except Exception as e:
            last_err = e
            logger.warning(f"Attempt {attempt + 1} failed: {str(e)}")
            time.sleep(1 * (attempt + 1))

    logger.error(f"All download retries failed for {url}")
    raise CustomException(CustomError.DOWNLOAD_FILE_FAILED) if not isinstance(last_err, CustomException) else last_err
