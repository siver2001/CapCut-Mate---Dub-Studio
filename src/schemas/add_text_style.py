from pydantic import BaseModel, Field

class AddTextStyleRequest(BaseModel):
    """request parameters"""
    text: str = Field(..., description='')
    keyword: str = Field(..., description='， | ')
    font_size: int = Field(default=12, description='Font size')
    keyword_color: str = Field(default='#ff7100', description='（Hex）')
    keyword_font_size: int = Field(default=15, description='Font size')

class AddTextStyleResponse(BaseModel):
    """response parameters"""
    text_style: str = Field(default='', description='JSONstring')