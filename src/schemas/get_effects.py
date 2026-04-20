from pydantic import BaseModel, Field
from typing import List, Optional

class GetEffectsRequest(BaseModel):
    """Geteffectlistrequest parameters"""
    mode: Optional[int] = Field(default=0, ge=0, le=2, description='effect，0=，1=VIP，2=， 0')

class EffectItem(BaseModel):
    """effectinfo"""
    name: str = Field(..., description='effect')
    is_vip: bool = Field(..., description='Whether to VIP effect')
    resource_id: str = Field(..., description=' ID')
    effect_id: str = Field(..., description=' ID')
    icon_url: str = Field(..., description=' URL')
    has_params: bool = Field(..., description='Whether to')

class GetEffectsResponse(BaseModel):
    """Geteffectlistresponse parameters"""
    effects: List[EffectItem] = Field(..., description='effectobjectarray')