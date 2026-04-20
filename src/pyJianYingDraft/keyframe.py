import uuid

from enum import Enum
from typing import Dict, List, Any

class Keyframe:
    """A keyframe (key point), currently only linear interpolation is supported"""

    kf_id: str
    """Global keyframe ID, auto-generated"""
    time_offset: int
    """Time offset relative to material start in microseconds"""
    values: List[float]
    """Keyframe values, usually only contains one element"""

    def __init__(self, time_offset: int, value: float):
        """Initialize a keyframe with given time offset and value"""
        self.kf_id = uuid.uuid4().hex

        self.time_offset = time_offset
        self.values = [value]

    def export_json(self) -> Dict[str, Any]:
        return {
            # Default values
            "curveType": "Line",
            "graphID": "",
            "left_control": {"x": 0.0, "y": 0.0},
            "right_control": {"x": 0.0, "y": 0.0},
            # Custom properties
            "id": self.kf_id,
            "time_offset": self.time_offset,
            "values": self.values
        }

class KeyframeProperty(Enum):
    """Property types controlled by keyframes"""

    position_x = "KFTypePositionX"
    """Right is positive. Value should be `value in CapCut` / `Draft Width`, i.e., unit is half canvas width."""
    position_y = "KFTypePositionY"
    """Up is positive. Value should be `value in CapCut` / `Draft Height`, i.e., unit is half canvas height."""
    rotation = "KFTypeRotation"
    """Rotation **angle** clockwise."""

    scale_x = "KFTypeScaleX"
    """X-axis scale ratio (1.0 for no scaling), mutually exclusive with `uniform_scale`."""
    scale_y = "KFTypeScaleY"
    """Y-axis scale ratio (1.0 for no scaling), mutually exclusive with `uniform_scale`."""
    uniform_scale = "UNIFORM_SCALE"
    """Simultaneous X and Y axis scale ratio (1.0 for no scaling), mutually exclusive with `scale_x` and `scale_y`."""

    alpha = "KFTypeAlpha"
    """Opacity, 1.0 is fully opaque, only valid for `VideoSegment`."""
    saturation = "KFTypeSaturation"
    """Saturation, 0.0 is original, range -1.0 to 1.0, only valid for `VideoSegment`."""
    contrast = "KFTypeContrast"
    """Contrast, 0.0 is original, range -1.0 to 1.0, only valid for `VideoSegment`."""
    brightness = "KFTypeBrightness"
    """Brightness, 0.0 is original, range -1.0 to 1.0, only valid for `VideoSegment`."""

    volume = "KFTypeVolume"
    """Volume, 1.0 is original, only valid for `AudioSegment` and `VideoSegment`."""

class KeyframeList:
    """Keyframe list, records a series of keyframes related to a specific property"""

    list_id: str
    """Global keyframe list ID, auto-generated"""
    keyframe_property: KeyframeProperty
    """Property controlled by keyframes"""
    keyframes: List[Keyframe]
    """List of keyframes"""

    def __init__(self, keyframe_property: KeyframeProperty):
        """Initialize keyframe list for given property"""
        self.list_id = uuid.uuid4().hex

        self.keyframe_property = keyframe_property
        self.keyframes = []

    def add_keyframe(self, time_offset: int, value: float):
        """Add a keyframe to the list with given time offset and value"""
        keyframe = Keyframe(time_offset, value)
        self.keyframes.append(keyframe)
        self.keyframes.sort(key=lambda x: x.time_offset)

    def export_json(self) -> Dict[str, Any]:
        return {
            "id": self.list_id,
            "keyframe_list": [kf.export_json() for kf in self.keyframes],
            "material_id": "",
            "property_type": self.keyframe_property.value
        }
