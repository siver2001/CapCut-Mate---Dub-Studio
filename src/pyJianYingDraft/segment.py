"""Define segment base class and some common attribute classes"""

import uuid
from typing import Optional, Dict, List, Any, Union

from .animation import SegmentAnimations
from .time_util import Timerange, tim
from .keyframe import KeyframeList, KeyframeProperty

class BaseSegment:
    """Segment base class"""

    segment_id: str
    """Global segment ID, auto-generated"""
    material_id: str
    """ID of material used"""
    target_timerange: Timerange
    """Segment time range on track"""

    common_keyframes: List[KeyframeList]
    """Keyframe list for various attributes"""

    def __init__(self, material_id: str, target_timerange: Timerange):
        self.segment_id = uuid.uuid4().hex
        self.material_id = material_id
        self.target_timerange = target_timerange

        self.common_keyframes = []

    @property
    def start(self) -> int:
        """Segment start time in microseconds"""
        return self.target_timerange.start
    @start.setter
    def start(self, value: int):
        self.target_timerange.start = value

    @property
    def duration(self) -> int:
        """Segment duration in microseconds"""
        return self.target_timerange.duration
    @duration.setter
    def duration(self, value: int):
        self.target_timerange.duration = value

    @property
    def end(self) -> int:
        """Segment end time in microseconds"""
        return self.target_timerange.end

    def overlaps(self, other: "BaseSegment") -> bool:
        """Determine if overlaps with another segment"""
        return self.target_timerange.overlaps(other.target_timerange)

    def export_json(self) -> Dict[str, Any]:
        """Return attributes common to all segment types"""
        return {
            "enable_adjust": True,
            "enable_color_correct_adjust": False,
            "enable_color_curves": True,
            "enable_color_match_adjust": False,
            "enable_color_wheels": True,
            "enable_lut": True,
            "enable_smart_color_adjust": False,
            "last_nonzero_volume": 1.0,
            "reverse": False,
            "track_attribute": 0,
            "track_render_index": 0,
            "visible": True,
            # Write custom fields
            "id": self.segment_id,
            "material_id": self.material_id,
            "target_timerange": self.target_timerange.export_json(),

            "common_keyframes": [kf_list.export_json() for kf_list in self.common_keyframes],
            "keyframe_refs": [],  # Purpose unclear
        }

class Speed:
    """Playback speed object, currently only supports fixed speed"""

    global_id: str
    """Global ID, auto-generated"""
    speed: float
    """Playback speed"""

    def __init__(self, speed: float):
        self.global_id = uuid.uuid4().hex
        self.speed = speed

    def export_json(self) -> Dict[str, Any]:
        return {
            "curve_speed": None,
            "id": self.global_id,
            "mode": 0,
            "speed": self.speed,
            "type": "speed"
        }

class AudioFade:
    """Audio fade-in/out effect"""

    fade_id: str
    """Global ID for fade effect, auto-generated"""

    in_duration: int
    """Fade-in duration in microseconds"""
    out_duration: int
    """Fade-out duration in microseconds"""

    def __init__(self, in_duration: int, out_duration: int):
        """Construct a fade effect with specified in/out durations"""

        self.fade_id = uuid.uuid4().hex
        self.in_duration = in_duration
        self.out_duration = out_duration

    def export_json(self) -> Dict[str, Any]:
        return {
            "id": self.fade_id,
            "fade_in_duration": self.in_duration,
            "fade_out_duration": self.out_duration,
            "fade_type": 0,
            "type": "audio_fade"
        }

class ClipSettings:
    """Image adjustment settings for material segments"""

    alpha: float
    """Image opacity, 0-1"""
    flip_horizontal: bool
    """Whether to flip horizontally"""
    flip_vertical: bool
    """Whether to flip vertically"""
    rotation: float
    """Clockwise rotation **angle**, can be positive or negative"""
    scale_x: float
    """Horizontal scale ratio"""
    scale_y: float
    """Vertical scale ratio"""
    transform_x: float
    """Horizontal translation, unit is half of canvas width"""
    transform_y: float
    """Vertical translation, unit is half of canvas height"""

    def __init__(self, *, alpha: float = 1.0,
                 flip_horizontal: bool = False, flip_vertical: bool = False,
                 rotation: float = 0.0,
                 scale_x: float = 1.0, scale_y: float = 1.0,
                 transform_x: float = 0.0, transform_y: float = 0.0):
        """Initialize image adjustment settings, default to no transformation

        Args:
            alpha (float, optional): Image opacity, 0-1. Default 1.0.
            flip_horizontal (bool, optional): Whether to flip horizontally. Default False.
            flip_vertical (bool, optional): Whether to flip vertically. Default False.
            rotation (float, optional): Clockwise rotation **angle**. Default 0.0.
            scale_x (float, optional): Horizontal scale ratio. Default 1.0.
            scale_y (float, optional): Vertical scale ratio. Default 1.0.
            transform_x (float, optional): Horizontal translation (half canvas width). Default 0.0.
            transform_y (float, optional): Vertical translation (half canvas height). Default 0.0.
                Note: Subtitles imported by CapCut seem to use -0.8 here.
        """
        self.alpha = alpha
        self.flip_horizontal, self.flip_vertical = flip_horizontal, flip_vertical
        self.rotation = rotation
        self.scale_x, self.scale_y = scale_x, scale_y
        self.transform_x, self.transform_y = transform_x, transform_y

    def export_json(self) -> Dict[str, Any]:
        clip_settings_json = {
            "alpha": self.alpha,
            "flip": {"horizontal": self.flip_horizontal, "vertical": self.flip_vertical},
            "rotation": self.rotation,
            "scale": {"x": self.scale_x, "y": self.scale_y},
            "transform": {"x": self.transform_x, "y": self.transform_y}
        }
        return clip_settings_json

class MediaSegment(BaseSegment):
    """Media segment base class"""

    source_timerange: Optional[Timerange]
    """Time range of source material clip, non-existent for stickers"""
    speed: Speed
    """Playback speed settings"""
    volume: float
    """Volume"""
    change_pitch: bool
    """Whether to follow pitch change with speed"""

    extra_material_refs: List[str]
    """Additional material IDs for linking animations/effects, etc."""

    def __init__(self, material_id: str, source_timerange: Optional[Timerange], target_timerange: Timerange,
                 speed: float, volume: float, change_pitch: bool):
        super().__init__(material_id, target_timerange)

        self.source_timerange = source_timerange
        self.speed = Speed(speed)
        self.volume = volume
        self.change_pitch = change_pitch

        self.extra_material_refs = [self.speed.global_id]

    def export_json(self) -> Dict[str, Any]:
        """Return default attributes common to audio and video segments"""
        ret = super().export_json()
        ret.update({
            "source_timerange": self.source_timerange.export_json() if self.source_timerange else None,
            "speed": self.speed.speed,
            "volume": self.volume,
            "extra_material_refs": self.extra_material_refs,
            "is_tone_modify": self.change_pitch,
        })
        return ret

class VisualSegment(MediaSegment):
    """Visual segment base class for all visible segments (video, sticker, text)"""

    clip_settings: ClipSettings
    """Image adjustment settings, can be overridden by keyframes"""

    uniform_scale: bool
    """Whether to lock XY scale ratio"""

    animations_instance: Optional[SegmentAnimations]
    """Animation instance, can be None
    
    Auto-added to material list when placed on track
    """

    def __init__(self, material_id: str, source_timerange: Optional[Timerange], target_timerange: Timerange,
                 speed: float, volume: float, change_pitch: bool, *, clip_settings: Optional[ClipSettings]):
        """Initialize visual segment base class

        Args:
            material_id (`str`): Material ID
            source_timerange (`Timerange`, optional): Source clip time range
            target_timerange (`Timerange`): Target time range on track
            speed (`float`): Playback speed
            volume (`float`): Volume
            change_pitch (`bool`): Whether to follow pitch change with speed
            clip_settings (`ClipSettings`, optional): Image adjustment settings, defaults to no change
        """
        super().__init__(material_id, source_timerange, target_timerange, speed, volume, change_pitch)

        self.clip_settings = clip_settings if clip_settings is not None else ClipSettings()
        self.uniform_scale = True
        self.animations_instance = None

    def add_keyframe(self, _property: KeyframeProperty, time_offset: Union[int, str], value: float) -> "VisualSegment":
        """Create a keyframe for a given property and add it to the list

        Args:
            _property (`KeyframeProperty`): Property to control
            time_offset (`int` or `str`): Time offset in microseconds. Parsed via `tim()` if string.
            value (`float`): Property value at `time_offset`

        Raises:
            `ValueError`: Attempting to set both `uniform_scale` and `scale_x`/`scale_y`
        """
        if (_property == KeyframeProperty.scale_x or _property == KeyframeProperty.scale_y) and self.uniform_scale:
            self.uniform_scale = False
        elif _property == KeyframeProperty.uniform_scale:
            if not self.uniform_scale:
                raise ValueError("Cannot set uniform_scale when scale_x or scale_y is already set")
            _property = KeyframeProperty.scale_x

        if isinstance(time_offset, str): time_offset = tim(time_offset)

        for kf_list in self.common_keyframes:
            if kf_list.keyframe_property == _property:
                kf_list.add_keyframe(time_offset, value)
                return self
        kf_list = KeyframeList(_property)
        kf_list.add_keyframe(time_offset, value)
        self.common_keyframes.append(kf_list)
        return self

    def export_json(self) -> Dict[str, Any]:
        """Export JSON data common to all visual segments"""
        json_dict = super().export_json()
        json_dict.update({
            "clip": self.clip_settings.export_json(),
            "uniform_scale": {"on": self.uniform_scale, "value": 1.0},
        })
        return json_dict
