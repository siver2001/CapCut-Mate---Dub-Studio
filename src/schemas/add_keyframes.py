from pydantic import BaseModel, Field
from typing import List

class AddKeyframesRequest(BaseModel):
    """Add keyframes request parameters"""
    draft_url: str = Field(default='', description='Draft URL')
    keyframes: str = Field(default='', description='List of keyframe info, represented as a JSON string')

class KeyframeItem(BaseModel):
    """Individual keyframe info"""
    segment_id: str = Field(..., description='Unique ID of the target segment')
    property: str = Field(..., description='Animation property type (KFTypePositionX, KFTypePositionY, KFTypeScaleX, KFTypeScaleY, KFTypeRotation, KFTypeAlpha)')
    offset: float = Field(..., ge=0.0, le=1.0, description='Keyframe time offset within the segment (0-1 range)')
    value: float = Field(..., description='Value of the property at that time offset')

class AddKeyframesResponse(BaseModel):
    """Add keyframes response parameters"""
    draft_url: str = Field(default='', description='Draft URL')
    keyframes_added: int = Field(default=0, description='Number of keyframes added')
    affected_segments: List[str] = Field(default=[], description='List of affected segment IDs')