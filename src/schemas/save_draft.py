from pydantic import BaseModel, Field

class SaveDraftRequest(BaseModel):
    """Save draft request parameters"""
    draft_url: str = Field(default='', description='Draft URL')

class SaveDraftResponse(BaseModel):
    """Save draft response parameters"""
    draft_url: str = Field(default='', description='Draft URL')