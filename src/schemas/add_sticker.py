from pydantic import BaseModel, Field

class AddStickerRequest(BaseModel):
    """Add sticker request parameters"""
    draft_url: str = Field(..., description='Draft URL')
    sticker_id: str = Field(..., description='Unique ID of the sticker')
    start: int = Field(..., description='Sticker start time (microseconds)')
    end: int = Field(..., description='Sticker end time (microseconds)')
    scale: float = Field(default=1.0, description='Sticker scale factor, recommended range [0.1, 5.0]')
    transform_x: int = Field(default=0, description='X-axis position offset (pixels), relative to canvas center')
    transform_y: int = Field(default=0, description='Y-axis position offset (pixels), relative to canvas center')

class AddStickerResponse(BaseModel):
    """Add sticker response parameters"""
    draft_url: str = Field(default='', description='Draft URL')
    sticker_id: str = Field(default='', description='Unique ID of the sticker')
    track_id: str = Field(default='', description='Track ID')
    segment_id: str = Field(default='', description='Segment ID')
    duration: int = Field(default=0, description='Sticker display duration (microseconds)')