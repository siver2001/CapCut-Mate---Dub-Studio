"""
Data model definition for video generation status query
"""
from typing import Optional
from pydantic import BaseModel, Field

class GenVideoStatusRequest(BaseModel):
    """Request model for querying video generation status"""
    draft_url: str = Field(..., description='Draft URL')

class GenVideoStatusResponse(BaseModel):
    """Response model for querying video generation status"""
    draft_url: str = Field(..., description='Draft URL')
    status: str = Field(..., description='Task status: pending, processing, completed, failed')
    progress: int = Field(..., description='Task progress (0-100)')
    video_url: str = Field(default='', description='Generated video URL (only when status is completed)')
    error_message: str = Field(default='', description='Error message (only when status is failed)')
    created_at: Optional[str] = Field(default=None, description='Task creation time')
    started_at: Optional[str] = Field(default=None, description='Task start time')
    completed_at: Optional[str] = Field(default=None, description='Task completion time')