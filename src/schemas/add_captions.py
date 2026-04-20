from pydantic import BaseModel, Field
from typing import List, Optional

class ShadowInfo(BaseModel):
    """Text shadow parameters"""
    shadow_alpha: float = Field(default=1.0, ge=0.0, le=1.0, description='Shadow opacity, range [0, 1]')
    shadow_color: str = Field(default='#000000', description='Shadow color (Hex)')
    shadow_diffuse: float = Field(default=15.0, ge=0.0, le=100.0, description='Shadow blur/diffusion degree, range [0, 100]')
    shadow_distance: float = Field(default=5.0, ge=0.0, le=100.0, description='Shadow distance from text, range [0, 100]')
    shadow_angle: float = Field(default=-45.0, ge=-180.0, le=180.0, description='Shadow offset angle, range [-180, 180]')

class AddCaptionsRequest(BaseModel):
    """Bulk add captions request parameters"""
    draft_url: str = Field(default='', description='Draft URL')
    captions: str = Field(default='', description='List of caption info, represented as a JSON string')
    text_color: str = Field(default='#ffffff', description='Text color (Hex)')
    border_color: Optional[str] = Field(default=None, description='Border color (Hex)')
    alignment: int = Field(default=1, ge=0, le=5, description='Text alignment (0-5)')
    alpha: float = Field(default=1.0, ge=0.0, le=1.0, description='Text transparency (0.0-1.0)')
    font: Optional[str] = Field(default=None, description='Font name')
    font_size: int = Field(default=15, ge=1, description='Font size')
    letter_spacing: Optional[float] = Field(default=None, description='Character spacing')
    line_spacing: Optional[float] = Field(default=None, description='Line spacing')
    scale_x: float = Field(default=1.0, description='Horizontal scale')
    scale_y: float = Field(default=1.0, description='Vertical scale')
    transform_x: float = Field(default=0.0, description='Horizontal offset')
    transform_y: float = Field(default=0.0, description='Vertical offset')
    style_text: bool = Field(default=False, description='Whether to use styled text')
    underline: bool = Field(default=False, description='Underline toggle')
    italic: bool = Field(default=False, description='Italic toggle')
    bold: bool = Field(default=False, description='Bold toggle')
    has_shadow: bool = Field(default=False, description='Whether to enable text shadow')
    shadow_info: Optional[ShadowInfo] = Field(default=None, description='Text shadow parameters')
    text_effect: Optional[str] = Field(default=None, description="Text effect name or effect_id, e.g., 'White text orange glow'")

class CaptionItem(BaseModel):
    """Individual caption info"""
    start: int = Field(..., description='Caption start time (microseconds)')
    end: int = Field(..., description='Caption end time (microseconds)')
    text: str = Field(..., description='Caption text content')
    keyword: Optional[str] = Field(default=None, description='Keywords (separated by |)')
    keyword_color: str = Field(default='#ff7100', description='Keyword color')
    keyword_border_color: Optional[str] = Field(default=None, description='Keyword border color')
    keyword_font_size: int = Field(default=15, ge=1, description='Keyword font size')
    font_size: int = Field(default=15, ge=1, description='Text font size')
    in_animation: Optional[str] = Field(default=None, description='Entrance animation name')
    out_animation: Optional[str] = Field(default=None, description='Exit animation name')
    loop_animation: Optional[str] = Field(default=None, description='Loop animation name')
    in_animation_duration: Optional[int] = Field(default=None, description='Entrance animation duration')
    out_animation_duration: Optional[int] = Field(default=None, description='Exit animation duration')
    loop_animation_duration: Optional[int] = Field(default=None, description='Loop animation duration')
    text_effect: Optional[str] = Field(default=None, description='Text effect name or effect_id')

class SegmentInfo(BaseModel):
    """info"""
    id: str = Field(..., description='Segment ID')
    start: int = Field(..., description='Start time（microseconds）')
    end: int = Field(..., description='（microseconds）')

class AddCaptionsResponse(BaseModel):
    """Addcaptionresponse parameters"""
    draft_url: str = Field(default='', description='Draft URL')
    track_id: str = Field(default='', description='captiontrackID')
    text_ids: List[str] = Field(default=[], description='captionIDlist')
    segment_ids: List[str] = Field(default=[], description='captionList of segment IDs')
    segment_infos: List[SegmentInfo] = Field(default=[], description='infolist')