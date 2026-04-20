from pydantic import BaseModel, Field
from typing import List, Optional
from .audio_timelines import TimelineItem

class ImgsInfosRequest(BaseModel):
    """imageinforequest parameters"""
    imgs: List[str] = Field(..., description='imageURLlist')
    timelines: List[TimelineItem] = Field(..., description='timelinearray')
    height: Optional[int] = Field(None, description='Video height')
    width: Optional[int] = Field(None, description='Video width')
    in_animation: Optional[str] = Field(None, description='Entrance animation，|')
    in_animation_duration: Optional[int] = Field(None, description='Entrance animationduration')
    loop_animation: Optional[str] = Field(None, description='，|')
    loop_animation_duration: Optional[int] = Field(None, description='duration')
    out_animation: Optional[str] = Field(None, description='Exit animation，|')
    out_animation_duration: Optional[int] = Field(None, description='Exit animationduration')
    transition: Optional[str] = Field(None, description='')
    transition_duration: Optional[int] = Field(None, description='duration')

class ImgsInfosResponse(BaseModel):
    """imageinforesponse parameters"""
    infos: str = Field(..., description='JSONstringimageinfo')