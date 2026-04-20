from pydantic import BaseModel, Field
from typing import List

class TimelineItem(BaseModel):
    """timeline"""
    start: int = Field(..., description='Start time')
    end: int = Field(..., description='')

class TimelinesRequest(BaseModel):
    """timelinerequest parameters"""
    duration: int = Field(..., description='duration')
    num: int = Field(..., description='timeline，2duration2')
    start: int = Field(..., description='Start time')
    type: int = Field(..., description='0: ，1：')

class TimelinesResponse(BaseModel):
    """timelineresponse parameters"""
    timelines: List[TimelineItem] = Field(..., description='timelinelist')
    all_timelines: List[TimelineItem] = Field(..., description='fulltimelinelist')