from pydantic import BaseModel, Field
from typing import List, Optional

class SegmentInfoItem(BaseModel):
    """track"""
    id: str = Field(..., description='Segment ID')
    start: int = Field(..., description='Start time（microseconds）')
    end: int = Field(..., description='（microseconds）')

class KeyframesInfosRequest(BaseModel):
    """keyframeinforequest parameters"""
    ctype: str = Field(..., description='keyframe：KFTypePositionX: X，width，width KFTypePositionY: Y，height，height KFTypeRotation: angle，0-360 UNIFORM_SCALE: ，0.01-5 KFTypeAlpha: Transparency，0-1')
    offsets: str = Field(..., description='keyframe，eg：0|100 ，0|50|100，，3keyframe')
    values: str = Field(..., description='offsets，，1|2，1|2|1')
    segment_infos: List[SegmentInfoItem] = Field(..., description='track，objectarray')
    height: Optional[int] = Field(None, description='video，')
    width: Optional[int] = Field(None, description='video，')

class KeyframesInfosResponse(BaseModel):
    """keyframeinforesponse parameters"""
    keyframes_infos: str = Field(..., description='JSONstringkeyframeinfo')