import os
import datetime
import config
from qcloud_cos import CosConfig
from qcloud_cos import CosS3Client
from src.utils.logger import logger
from exceptions import CustomException, CustomError

def cos_upload_file(file_path: str, expire_days: int=1) -> str:
    """
    上传File到COS，返回带签名的临时URL，File会在指定days数后Auto过期


    Args:
    file_path: FilePath
    expire_days: URL有效期days数，默认1days


    Returns:
    str: 带签名的临时下载URL（有效期asexpire_daysdays）


    Raises:
    CustomException: 上传Failure
"""
    cfg = CosConfig(Region=config.COS_REGION, SecretId=config.COS_SECRET_ID, SecretKey=config.COS_SECRET_KEY, Token=None)
    cli = CosS3Client(cfg)
    try:
        now = datetime.datetime.now()
        current_date = now.strftime('%Y-%m-%d')
        current_hour = now.strftime('%H')
        filename = os.path.basename(file_path)
        key = f'{current_date}/{current_hour}/{filename}'
        expire_time = datetime.datetime.now() + datetime.timedelta(days=expire_days)
        expire_time_str = expire_time.strftime('%Y-%m-%dT%H:%M:%S.000Z')
        response = cli.upload_file(Bucket=config.COS_BUCKET_NAME, Key=key, LocalFilePath=file_path)
        logger.info(f'COS upload success, key: {key}, expire time: {expire_time_str}, response: {response}')
        signed_url = cli.get_presigned_url(Method='GET', Bucket=config.COS_BUCKET_NAME, Key=key, Expired=expire_days * 24 * 3600)
        logger.info(f'Generated signed URL valid for {expire_days} day(s), URL: {signed_url[:100]}...')
        return signed_url
    except Exception as e:
        logger.error(f'COS upload failed: {e}')
        raise CustomException(CustomError.INTERNAL_SERVER_ERROR, 'COS upload failed')