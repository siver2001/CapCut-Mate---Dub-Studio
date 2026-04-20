from pydantic import BaseModel, Field
from typing import List, Optional

class SceneTimelineItem(BaseModel):
    """Scene timeline item"""
    start: int = Field(..., description='Scene start time (microseconds)')
    end: int = Field(..., description='Scene end time (microseconds)')

class AddVideosRequest(BaseModel):
    """Bulk add videos request parameters"""
    draft_url: str = Field(default='', description='Draft URL')
    video_infos: str = Field(default='', description='List of video info, represented as a JSON string')
    scene_timelines: Optional[List[SceneTimelineItem]] = Field(default=None, description='List of scene timelines for video speed adjustment')
    alpha: float = Field(default=1.0, description='Global opacity [0, 1]')
    scale_x: float = Field(default=1.0, description='X-axis scale factor, recommended range [0.1, 5.0]')
    scale_y: float = Field(default=1.0, description='Y-axis scale factor, recommended range [0.1, 5.0]')
    transform_x: int = Field(default=0, description='X-axis location offset (pixels)')
    transform_y: int = Field(default=0, description='Y-axis location offset (pixels)')

class AddVideosResponse(BaseModel):
    """Addvideoresponse parameters"""
    draft_url: str = Field(default='', description='Draft URL')
    track_id: str = Field(default='', description='trackID')
    video_ids: List[str] = Field(default=[], description='videoIDlist')
    segment_ids: List[str] = Field(default=[], description='List of segment IDs')