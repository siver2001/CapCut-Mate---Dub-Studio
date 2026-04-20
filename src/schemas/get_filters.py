from pydantic import BaseModel, Field
from typing import List, Optional

class GetFiltersRequest(BaseModel):
    """Getfilterlistrequest parameters"""
    mode: Optional[int] = Field(default=0, ge=0, le=2, description='filter，0=，1=VIP，2=， 0')

class FilterItem(BaseModel):
    """filterinfo"""
    name: str = Field(..., description='filter')
    is_vip: bool = Field(..., description='Whether to VIP filter')
    resource_id: str = Field(..., description=' ID')
    effect_id: str = Field(..., description=' ID')
    has_params: bool = Field(..., description='Whether to')

class GetFiltersResponse(BaseModel):
    """Getfilterlistresponse parameters"""
    filters: List[FilterItem] = Field(..., description='filterobjectarray')