import uuid
from pydantic import BaseModel, Field
from pydantic.functional_validators import field_validator
from typing import Optional

class GenVideoRequest(BaseModel):
    """Exportvideo"""
    draft_url: str = Field(default='', description='Draft URL')
    apiKey: Optional[str] = Field(default=None, description='apiKeyUUID')

    @field_validator('apiKey')
    @classmethod
    def validate_api_key(cls, v):
        if v is None or v == '':
            return None
            try:
                uuid.UUID(v)
            except ValueError:
                raise ValueError('API密钥格式不正确，must 是valid 的UUID')
                return v

class GenVideoResponse(BaseModel):
    """Generatevideoresponse parameters"""
    message: str = Field(..., description='')