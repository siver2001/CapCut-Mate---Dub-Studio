"""Defines effect/filter segment classes"""

from typing import Union, Optional, List

from .time_util import Timerange
from .segment import BaseSegment
from .video_segment import VideoEffect, Filter

from .metadata import VideoSceneEffectType, VideoCharacterEffectType, FilterType

class EffectSegment(BaseSegment):
    """Effect segment placed on an independent effect track"""

    effect_inst: VideoEffect
    """Corresponding effect material

    Automatically added to the material list when placed on a track
    """

    def __init__(self, effect_type: Union[VideoSceneEffectType, VideoCharacterEffectType],
                 target_timerange: Timerange, params: Optional[List[Optional[float]]] = None):
        self.effect_inst = VideoEffect(effect_type, params, apply_target_type=2)  # Global scope
        super().__init__(self.effect_inst.global_id, target_timerange)

class FilterSegment(BaseSegment):
    """Filter segment placed on an independent filter track"""

    material: Filter
    """Corresponding filter material

    Automatically added to the material list when placed on a track
    """

    def __init__(self, meta: FilterType, target_timerange: Timerange, intensity: float):
        self.material = Filter(meta.value, intensity)
        super().__init__(self.material.global_id, target_timerange)
