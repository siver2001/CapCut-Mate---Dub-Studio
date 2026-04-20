from pydantic import BaseModel, Field

class GetUrlRequest(BaseModel):
    """extractrequest parameters"""
    output: str = Field(..., description='extract')

class GetUrlResponse(BaseModel):
    """extractresponse parameters"""
    output: str = Field(..., description='extract')