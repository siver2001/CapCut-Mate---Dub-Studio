"""
GetimageEntrance animation
"""
from typing import Literal, List
from pydantic import BaseModel, Field

class GetImageAnimationsRequest(BaseModel):
    """GetimageEntrance animation"""
    mode: int = Field(default=0, description='：0=，1=VIP，2=')
    type: Literal['in', 'out', 'loop'] = Field(..., description='：in=，out=，loop=')

class ImageAnimationItem(BaseModel):
    """Individualimage"""
    resource_id: str = Field(..., description='ID')
    type: str = Field(..., description='')
    category_id: str = Field(..., description='ID')
    category_name: str = Field(..., description='')
    duration: int = Field(..., description='duration（microseconds）')
    id: str = Field(..., description='unique IDID')
    name: str = Field(..., description='')
    request_id: str = Field(default='', description='ID')
    start: int = Field(default=0, description='Start time')
    icon_url: str = Field(..., description='URL')
    material_type: str = Field(default='sticker', description='material')
    panel: str = Field(default='', description='info')
    path: str = Field(default='', description='info')
    platform: str = Field(default='all', description='')

class GetImageAnimationsResponse(BaseModel):
    """GetimageEntrance animation"""
    effects: List[ImageAnimationItem] = Field(..., description='imageEntrance animationobjectarray')