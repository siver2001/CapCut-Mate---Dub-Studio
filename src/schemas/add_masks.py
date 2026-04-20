from pydantic import BaseModel, Field
from typing import List

class AddMasksRequest(BaseModel):
    """Add masks request parameters"""
    draft_url: str = Field(default='', description='Draft URL')
    segment_ids: List[str] = Field(default=[], description='List of segment IDs to apply the mask to')
    name: str = Field(default='linear', description='Mask type name')
    X: int = Field(default=0, description='Mask center X coordinate (pixels)')
    Y: int = Field(default=0, description='Mask center Y coordinate (pixels)')
    width: int = Field(default=512, description='Mask width (pixels)')
    height: int = Field(default=512, description='Mask height (pixels)')
    feather: int = Field(default=0, description='Feather amount (0-100)')
    rotation: int = Field(default=0, description='Rotation angle (degrees)')
    invert: bool = Field(default=False, description='Whether to invert the mask')
    roundCorner: int = Field(default=0, description='Round corner radius (0-100)')

class AddMasksResponse(BaseModel):
    """Add masks response parameters"""
    draft_url: str = Field(default='', description='Draft URL')
    masks_added: int = Field(default=0, description='Number of successfully added masks')
    affected_segments: List[str] = Field(default=[], description='List of affected segment IDs')
    mask_ids: List[str] = Field(default=[], description='List of mask IDs')