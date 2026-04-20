from pydantic import BaseModel, Field
from typing import List, Optional
from .audio_timelines import TimelineItem

class AudioInfosRequest(BaseModel):
    """audioinforequest parameters"""
    mp3_urls: List[str] = Field(..., description='audioURLarray')
    timelines: List[TimelineItem] = Field(..., description='timelinearray')
    audio_effect: Optional[str] = Field(None, description='audio')
    volume: Optional[float] = Field(None, description='')

class AudioInfosResponse(BaseModel):
    """audioinforesponse parameters"""
    infos: str = Field(..., description='JSONstringaudioinfo')