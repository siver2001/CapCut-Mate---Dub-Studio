from pydantic import BaseModel, Field

class CreateDraftRequest(BaseModel):
    """Create draft request parameters"""
    height: int = Field(default=1080, ge=1, description='Video height')
    width: int = Field(default=1920, ge=1, description='Video width')

class CreateDraftResponse(BaseModel):
    """Create draft response parameters"""
    draft_url: str = Field(default='', description='Draft URL')
    tip_url: str = Field(default='', description='Help documentation URL')