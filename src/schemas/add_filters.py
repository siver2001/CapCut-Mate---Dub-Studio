from pydantic import BaseModel, Field
from typing import List

class AddFiltersRequest(BaseModel):
    """Add filters request parameters"""
    draft_url: str = Field(default='', description='Draft URL')
    filter_infos: str = Field(default='', description='List of filter info, represented as a JSON string')

class FilterItem(BaseModel):
    """Individual filter info"""
    filter_title: str = Field(..., description='Filter title/name')
    start: int = Field(..., description='Filter start time (microseconds)')
    end: int = Field(..., description='Filter end time (microseconds)')
    intensity: float = Field(default=100.0, ge=0, le=100, description='Filter intensity (0-100)')

class AddFiltersResponse(BaseModel):
    """Add filters response parameters"""
    draft_url: str = Field(default='', description='Draft URL')
    track_id: str = Field(default='', description='Filter track ID')
    filter_ids: List[str] = Field(default=[], description='List of filter IDs')
    segment_ids: List[str] = Field(default=[], description='List of filter segment IDs')