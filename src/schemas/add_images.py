from pydantic import BaseModel, Field
from typing import List

class AddImagesRequest(BaseModel):
    """Bulk add images request parameters"""
    draft_url: str = Field(..., description='Draft URL')
    image_infos: str = Field(..., description='List of image info, represented as a JSON string')
    alpha: float = Field(default=1.0, description='Global opacity [0, 1]')
    scale_x: float = Field(default=1.0, description='X-axis scale factor')
    scale_y: float = Field(default=1.0, description='Y-axis scale factor')
    transform_x: int = Field(default=0, description='X-axis location offset (pixels)')
    transform_y: int = Field(default=0, description='Y-axis location offset (pixels)')

class SegmentInfo(BaseModel):
    """Segment info"""
    id: str = Field(..., description='Segment ID')
    start: int = Field(..., description='Start time (microseconds)')
    end: int = Field(..., description='End time (microseconds)')

class AddImagesResponse(BaseModel):
    """Add images response parameters"""
    draft_url: str = Field(default='', description='Draft URL')
    track_id: str = Field(default='', description='Video track ID')
    image_ids: List[str] = Field(default=[], description='List of image IDs')
    segment_ids: List[str] = Field(default=[], description='List of segment IDs')
    segment_infos: List[SegmentInfo] = Field(default=[], description='List of segment info')