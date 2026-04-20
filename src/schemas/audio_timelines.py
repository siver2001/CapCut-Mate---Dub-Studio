from pydantic import BaseModel, Field
from typing import List

class AudioTimelinesRequest(BaseModel):
    """audiotimelinerequest parameters"""
    links: List[str] = Field(..., description='audioURLarray')

class TimelineItem(BaseModel):
    """timeline"""
    start: int = Field(..., description='Start time（microseconds）')
    end: int = Field(..., description='（microseconds）')

class AudioTimelinesResponse(BaseModel):
    """audiotimelineresponse parameters"""
    timelines: List[TimelineItem] = Field(..., description='timelinelist')
    all_timelines: List[TimelineItem] = Field(..., description='fulltimelinelist')