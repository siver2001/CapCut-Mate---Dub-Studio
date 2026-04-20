"""Metadata type definitions"""

from enum import Enum

from typing import List, Dict, Any
from typing import TypeVar, Optional

class EffectParam:
    """Effect parameter information"""

    name: str
    """Parameter name"""
    default_value: float
    """Default value"""
    min_value: float
    """Minimum value"""
    max_value: float
    """Maximum value"""

    def __init__(self, name: str, default_value: float, min_value: float, max_value: float):
        self.name = name
        self.default_value = default_value
        self.min_value = min_value
        self.max_value = max_value

class EffectParamInstance(EffectParam):
    """Effect parameter instance"""

    index: int
    """Parameter index"""
    value: float
    """Current value"""

    def __init__(self, meta: EffectParam, index: int, value: float):
        super().__init__(meta.name, meta.default_value, meta.min_value, meta.max_value)
        self.index = index
        self.value = value

    def export_json(self) -> Dict[str, Any]:
        return {
            "default_value": self.default_value,
            "max_value": self.max_value,
            "min_value": self.min_value,
            "name": self.name,
            "parameterIndex": self.index,
            "portIndex": 0,
            "value": self.value
        }

# Base effect metadata, used directly for filters/text/video effects
class EffectMeta:
    """Effect metadata, used directly for filters/text/video effects"""

    name: str
    """Effect name"""
    is_vip: bool
    """Whether it's a VIP feature"""

    resource_id: str
    """Resource ID"""
    effect_id: str
    """Effect ID"""
    md5: str

    params: List[EffectParam]
    """Effect parameter information"""

    def __init__(self, name: str, is_vip: bool, resource_id: str, effect_id: str, md5: str, params: List[EffectParam] = []):
        self.name = name
        self.is_vip = is_vip
        self.resource_id = resource_id
        self.effect_id = effect_id
        self.md5 = md5
        self.params = params

    def parse_params(self, params: Optional[List[Optional[float]]]) -> List[EffectParamInstance]:
        """Parse parameter list (range 0~100), return list of parameter instances"""
        ret: List[EffectParamInstance] = []

        if params is None: params = []
        for i, param in enumerate(self.params):
            val = param.default_value
            if i < len(params):
                input_v = params[i]
                if input_v is not None:
                    if input_v < 0 or input_v > 100:
                        raise ValueError("Invalid parameter value %f within %s" % (input_v, str(param)))
                    val = param.min_value + (param.max_value - param.min_value) * input_v / 100.0  # Map 0~100 to actual value
            ret.append(EffectParamInstance(param, i, val))
        return ret


EffectEnumSubclass = TypeVar("EffectEnumSubclass", bound="EffectEnum")

class EffectEnum(Enum):
    """Effect enum base class, provides a `from_name` method to get metadata by name"""

    @classmethod
    def from_name(cls: "type[EffectEnumSubclass]", name: str) -> EffectEnumSubclass:
        """Get effect metadata by name, ignoring case, spaces and underscores

        Args:
            name (str): Effect name

        Raises:
            `ValueError`: Effect name does not exist
        """
        name = name.lower().replace(" ", "").replace("_", "")
        for effect in cls:
            if effect.name.lower().replace(" ", "").replace("_", "") == name:
                return effect
        raise ValueError(f"Effect named '{name}' not found")

# Animation metadata
class AnimationMeta:
    """Animation metadata, used for intro/outro/group animations of video/text segments"""

    title: str
    is_vip: bool
    duration: int
    """Default duration in microseconds"""

    resource_id: str
    effect_id: str
    md5: str

    def __init__(self, title: str, is_vip: bool, duration: float, resource_id: str, effect_id: str, md5: str):
        self.title = title
        self.is_vip = is_vip
        self.duration = int(round(duration * 1e6))
        self.resource_id = resource_id
        self.effect_id = effect_id
        self.md5 = md5

# Mask metadata
class MaskMeta:
    """Mask metadata"""

    name: str
    """Mask name"""

    resource_type: str
    """Resource type, related to mask shape"""

    resource_id: str
    """Resource ID"""
    effect_id: str
    """Effect ID"""
    md5: str

    default_aspect_ratio: float
    """Default aspect ratio (both width and height are relative to material)"""

    def __init__(self, name: str, resource_type: str, resource_id: str, effect_id: str, md5: str, default_aspect_ratio: float):
        self.name = name
        self.resource_type = resource_type
        self.resource_id = resource_id
        self.effect_id = effect_id
        self.md5 = md5

        self.default_aspect_ratio = default_aspect_ratio

# Transition metadata
class TransitionMeta:
    """Transition metadata"""

    name: str
    """Transition name"""
    is_vip: bool
    """Whether it's a VIP feature"""

    resource_id: str
    """Resource ID"""
    effect_id: str
    """Effect ID"""
    md5: str

    default_duration: int
    """Default duration in microseconds"""
    is_overlap: bool
    """Whether it allows overlap"""

    def __init__(self, name: str, is_vip: bool, resource_id: str, effect_id: str, md5: str, default_duration: float, is_overlap: bool):
        self.name = name
        self.is_vip = is_vip
        self.resource_id = resource_id
        self.effect_id = effect_id
        self.md5 = md5

        self.default_duration = int(round(default_duration * 1e6))
        self.is_overlap = is_overlap

