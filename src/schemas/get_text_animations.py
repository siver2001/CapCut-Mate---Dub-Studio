"""
GettextEntrance animation
"""
from typing import Literal, List
from pydantic import BaseModel, Field

class GetTextAnimationsRequest(BaseModel):
    """GettextEntrance animation"""
    mode: int = Field(default=0, description='：0=，1=VIP，2=')
    type: Literal['in', 'out', 'loop'] = Field(..., description='：in=，out=，loop=')

class TextAnimationItem(BaseModel):
    """Individualtext"""
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

class GetTextAnimationsResponse(BaseModel):
    """GettextEntrance animation"""
    effects: List[TextAnimationItem] = Field(..., description='textEntrance animationobjectarray')