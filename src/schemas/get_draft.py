from pydantic import BaseModel, Field
from typing import List

class GetDraftRequest(BaseModel):
    """Getrequest parameters"""
    draft_id: str = Field(..., min_length=20, max_length=32, description='Draft ID')

class GetDraftResponse(BaseModel):
    """Getresponse parameters"""
    files: List[str] = Field(default=[], description='list')