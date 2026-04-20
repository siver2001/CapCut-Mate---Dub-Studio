from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
from .audio_timelines import TimelineItem

class FilterInfosRequest(BaseModel):
    """filterinforequest parameters"""
    filters: List[str] = Field(..., description='filterlist')
    timelines: List[TimelineItem] = Field(..., description='timelinearray')
    intensities: Optional[List[float]] = Field(default=None, description='filterlist(0-100)，')

    @field_validator('intensities', mode='before')
    @classmethod
    def validate_intensities(cls, v):
        """ intensities array 0-100 """
        if v is None:
            return v
            return [max(0, min(100, val)) for val in v]

class FilterInfosResponse(BaseModel):
    """filterinforesponse parameters"""
    infos: str = Field(..., description='JSONstringfilterinfo')