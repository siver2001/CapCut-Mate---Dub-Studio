from pydantic import BaseModel, Field
from typing import List, Optional

class GetTextEffectsRequest(BaseModel):
    """Gettext effectlistrequest parameters"""
    mode: Optional[int] = Field(default=0, ge=0, le=2, description='text effect，0=，1=VIP，2=， 0')

class TextEffectItem(BaseModel):
    """text effectinfo"""
    id: str = Field(..., description='text effect ID')
    title: str = Field(..., description='text effect')
    is_vip: bool = Field(..., description='Whether to VIP ')

class GetTextEffectsResponse(BaseModel):
    """Gettext effectlistresponse parameters"""
    text_effects: List[TextEffectItem] = Field(..., description='text effectobjectarray')