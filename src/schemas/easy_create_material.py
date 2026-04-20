from pydantic import BaseModel, Field
from typing import Optional

class EasyCreateMaterialRequest(BaseModel):
    """Easy create material track request parameters"""
    draft_url: str = Field(..., description='Full URL of the target draft')
    audio_url: str = Field(..., description='Audio file URL, cannot be empty or null')
    text: Optional[str] = Field(default=None, description='Text content to add')
    img_url: Optional[str] = Field(default=None, description='Image file URL')
    video_url: Optional[str] = Field(default=None, description='Video file URL')
    text_color: str = Field(default='#ffffff', description='Text color (hex format)')
    font_size: int = Field(default=15, description='Font size')
    text_transform_y: int = Field(default=0, description='Text Y-axis position offset')

class EasyCreateMaterialResponse(BaseModel):
    """Easy create material track response parameters"""
    draft_url: str = Field(default='', description='Draft URL')