from pydantic import BaseModel, Field
from typing import List

class ObjItem(BaseModel):
    """object"""
    output: str = Field(..., description='URL')

class ObjsToStrListRequest(BaseModel):
    """objectlistconvert tostringlistrequest parameters"""
    outputs: List[ObjItem] = Field(..., description='object')

class ObjsToStrListResponse(BaseModel):
    """objectlistconvert tostringlistresponse parameters"""
    infos: List[str] = Field(..., description='stringlist')