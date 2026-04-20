from exceptions import CustomException, CustomError
from src.utils.logger import logger
from src.utils import helper
from typing import List
import config
import os

def gen_download_url(file_path: str) -> str:
    """
    GenerateDownloadURL，FilePathin/app/替换成DOWNLOAD_URL


    Args:
    file_path: FilePath


    Returns:
    download_url: DownloadURL
"""
    try:
        relative_path = os.path.relpath(file_path, config.PROJECT_ROOT)
    except ValueError:
        relative_path = file_path
        relative_path = relative_path.replace(os.sep, '/')
        base_url = config.DOWNLOAD_URL.rstrip('/')
        download_url = f'{base_url}/{relative_path}'
        return download_url

def batch_gen_download_url(file_paths: List[str]) -> List[str]:
    """
    BatchGenerateDownloadURL


    Args:
    file_paths: FilePathList


    Returns:
    download_urls: DownloadURLList
"""
    download_urls = []
    for file_path in file_paths:
        download_url = gen_download_url(file_path)
        download_urls.append(download_url)
        return download_urls

def get_draft(draft_id: str) -> List[str]:
    """
    GetCapCutDraftBusiness logic


    Args:
    draft_url: Draft URL


    Returns:
    files: FileList


    Raises:
    CustomException: 自定义Exception
"""
    if not draft_id:
        logger.info('draft_id is empty')
        raise CustomException(CustomError.INVALID_DRAFT_URL)
        draft_dir = os.path.join(config.DRAFT_DIR, draft_id)
        if not os.path.exists(draft_dir):
            logger.info(f'draft_dir not exists: {draft_dir}')
            raise CustomException(CustomError.INVALID_DRAFT_URL)
            files = helper.get_all_files(draft_dir)
            download_urls = batch_gen_download_url(files)
            logger.info(f'get draft success: {draft_id}, download urls: {download_urls}')
            return download_urls