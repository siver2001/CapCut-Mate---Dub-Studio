"""Track class and its metadata"""

import uuid

from enum import Enum
from typing import TypeVar, Generic, Type
from typing import Dict, List, Any, Union
from dataclasses import dataclass
from abc import ABC, abstractmethod

from .exceptions import SegmentOverlap
from .segment import BaseSegment
from .video_segment import VideoSegment, StickerSegment
from .audio_segment import AudioSegment
from .text_segment import TextSegment
from .effect_segment import EffectSegment, FilterSegment

@dataclass
class Track_meta:
    """Track metadata associated with track type"""

    segment_type: Union[Type[VideoSegment], Type[AudioSegment],
                        Type[EffectSegment], Type[FilterSegment],
                        Type[TextSegment], Type[StickerSegment], None]
    """Segment type associated with track"""
    render_index: int
    """Default rendering order, higher is closer to foreground"""
    allow_modify: bool
    """Whether modification is allowed when imported"""

class TrackType(Enum):
    """Track type enum

    Variable names correspond to the type attribute, values represent track metadata
    """

    video = Track_meta(VideoSegment, 0, True)
    audio = Track_meta(AudioSegment, 0, True)
    effect = Track_meta(EffectSegment, 10000, False)
    filter = Track_meta(FilterSegment, 11000, False)
    sticker = Track_meta(StickerSegment, 14000, False)
    text = Track_meta(TextSegment, 15000, True)  # Originally 14000, changed to 15000 to avoid conflict with sticker

    adjust = Track_meta(None, 0, False)
    """For import use only, do not try to create new tracks of this type"""

    @staticmethod
    def from_name(name: str) -> "TrackType":
        """Get track type enum by name"""
        for t in TrackType:
            if t.name == name:
                return t
        raise ValueError("Invalid track type: %s" % name)


class BaseTrack(ABC):
    """Track base class"""

    track_type: TrackType
    """Track type"""
    name: str
    """Track name"""
    track_id: str
    """Track global ID"""
    render_index: int
    """Rendering order, higher is closer to foreground"""

    @abstractmethod
    def export_json(self) -> Dict[str, Any]: ...

Seg_type = TypeVar("Seg_type", bound=BaseSegment)
class Track(BaseTrack, Generic[Seg_type]):
    """Track in non-template mode"""

    mute: bool
    """Whether muted"""

    segments: List[Seg_type]
    """List of segments contained in the track"""

    def __init__(self, track_type: TrackType, name: str, render_index: int, mute: bool):
        self.track_type = track_type
        self.name = name
        self.track_id = uuid.uuid4().hex
        self.render_index = render_index

        self.mute = mute
        self.segments = []

    @property
    def end_time(self) -> int:
        """Track end time in microseconds"""
        if len(self.segments) == 0:
            return 0
        return self.segments[-1].target_timerange.end

    @property
    def accept_segment_type(self) -> Type[Seg_type]:
        """Return segment type allowed for this track"""
        return self.track_type.value.segment_type  # type: ignore

    def add_segment(self, segment: Seg_type) -> "Track[Seg_type]":
        """Add a segment to the track. Segment must match track type and not overlap with existing segments.

        Args:
            segment (Seg_type): Segment to add

        Raises:
            `TypeError`: New segment type does not match track type
            `SegmentOverlap`: New segment overlaps with existing segments
        """
        if not isinstance(segment, self.accept_segment_type):
            raise TypeError("New segment (%s) is not of the same type as the track (%s)" % (type(segment), self.accept_segment_type))

        # Check for segment overlap
        for seg in self.segments:
            if seg.overlaps(segment):
                raise SegmentOverlap("New segment overlaps with existing segment [start: {}, end: {}]"
                                     .format(segment.target_timerange.start, segment.target_timerange.end))

        self.segments.append(segment)
        return self

    def export_json(self) -> Dict[str, Any]:
        # Write render_index for each segment
        segment_exports = [seg.export_json() for seg in self.segments]
        for seg in segment_exports:
            seg["render_index"] = self.render_index

        return {
            "attribute": int(self.mute),
            "flag": 0,
            "id": self.track_id,
            "is_default_name": len(self.name) == 0,
            "name": self.name,
            "segments": segment_exports,
            "type": self.track_type.name
        }
