from pydantic import BaseModel, Field
from typing import List

class AddAudiosRequest(BaseModel):
    """Bulk add audios request parameters"""
    draft_url: str = Field(..., description='Draft URL')
    audio_infos: str = Field(..., description='List of audio info, represented as a JSON string')

class AddAudiosResponse(BaseModel):
    """Add audios response parameters"""
    draft_url: str = Field(default='', description='Draft URL')
    track_id: str = Field(default='', description='Audio track ID')
    audio_ids: List[str] = Field(default=[], description='List of audio IDs')