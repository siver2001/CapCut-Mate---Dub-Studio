from pydantic import BaseModel, Field
from typing import List

class AddEffectsRequest(BaseModel):
    """Add effects request parameters"""
    draft_url: str = Field(default='', description='Draft URL')
    effect_infos: str = Field(default='', description='List of effect info, represented as a JSON string')

class EffectItem(BaseModel):
    """Individual effect info"""
    effect_title: str = Field(..., description='Effect title/name')
    start: int = Field(..., description='Effect start time (microseconds)')
    end: int = Field(..., description='Effect end time (microseconds)')

class AddEffectsResponse(BaseModel):
    """Add effects response parameters"""
    draft_url: str = Field(default='', description='Draft URL')
    track_id: str = Field(default='', description='Effect track ID')
    effect_ids: List[str] = Field(default=[], description='List of effect IDs')
    segment_ids: List[str] = Field(default=[], description='List of effect segment IDs')