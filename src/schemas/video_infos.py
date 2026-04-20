from pydantic import BaseModel, Field
from typing import List, Optional
from .audio_timelines import TimelineItem

class VideoInfosRequest(BaseModel):
    """videoinforequest parameters"""
    video_urls: List[str] = Field(..., description='videolist')
    timelines: List[TimelineItem] = Field(..., description='timelinearray')
    height: Optional[int] = Field(None, description='video')
    width: Optional[int] = Field(None, description='video')
    mask: Optional[str] = Field(None, description='video，：，，，')
    transition: Optional[str] = Field(None, description='')
    transition_duration: Optional[int] = Field(None, description='duration，')
    volume: Optional[float] = Field(1.0, description='float，，0-10,1')

class VideoInfosResponse(BaseModel):
    """videoinforesponse parameters"""
    infos: str = Field(..., description='JSONstringvideoinfo')