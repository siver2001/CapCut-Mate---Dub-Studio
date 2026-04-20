from pydantic import BaseModel, Field
from typing import List, Optional
from .audio_timelines import TimelineItem

class CaptionInfosRequest(BaseModel):
    """captioninforequest parameters"""
    texts: List[str] = Field(..., description='list')
    timelines: List[TimelineItem] = Field(..., description='timelinearray')
    font_size: Optional[int] = Field(None, description='Font size')
    keyword_color: Optional[str] = Field(None, description='')
    keyword_border_color: Optional[str] = Field(None, description='')
    keyword_font_size: Optional[int] = Field(None, description='Font size')
    keywords: Optional[List[str]] = Field(None, description='list')
    in_animation: Optional[str] = Field(None, description='Entrance animation')
    in_animation_duration: Optional[int] = Field(None, description='Entrance animationduration')
    loop_animation: Optional[str] = Field(None, description='')
    loop_animation_duration: Optional[int] = Field(None, description='duration')
    out_animation: Optional[str] = Field(None, description='Exit animation')
    out_animation_duration: Optional[int] = Field(None, description='Exit animationduration')
    transition: Optional[str] = Field(None, description='')
    transition_duration: Optional[int] = Field(None, description='duration')

class CaptionInfosResponse(BaseModel):
    """captioninforesponse parameters"""
    infos: str = Field(..., description='JSONstringcaptioninfo')