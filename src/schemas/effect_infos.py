from pydantic import BaseModel, Field
from typing import List
from .audio_timelines import TimelineItem

class EffectInfosRequest(BaseModel):
    """effectinforequest parameters"""
    effects: List[str] = Field(..., description='effectlist')
    timelines: List[TimelineItem] = Field(..., description='timelinearray')

class EffectInfosResponse(BaseModel):
    """effectinforesponse parameters"""
    infos: str = Field(..., description='JSONstringeffectinfo')