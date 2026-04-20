from pydantic import BaseModel, Field
from typing import List

class StickerPackage(BaseModel):
    """stickerinfo"""
    height_per_frame: int = Field(..., description='')
    size: int = Field(..., description='sticker')
    width_per_frame: int = Field(..., description='')

class LargeImage(BaseModel):
    """info"""
    image_url: str = Field(..., description='imageURL')

class StickerInfo(BaseModel):
    """stickerinfo"""
    large_image: LargeImage = Field(..., description='info')
    preview_cover: str = Field(..., description='')
    sticker_package: StickerPackage = Field(..., description='stickerinfo')
    sticker_type: int = Field(..., description='sticker')
    track_thumbnail: str = Field(..., description='track')

class StickerItem(BaseModel):
    """sticker"""
    sticker: StickerInfo = Field(..., description='stickerinfo')
    sticker_id: str = Field(..., description='stickerID')
    title: str = Field(..., description='sticker')

class SearchStickerRequest(BaseModel):
    """searchstickerrequest parameters"""
    keyword: str = Field(..., description='，')

class SearchStickerResponse(BaseModel):
    """searchstickerresponse parameters"""
    data: List[StickerItem] = Field(..., description='stickerlist')