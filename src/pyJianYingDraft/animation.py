"""Define video/text animation related classes"""

import uuid

from typing import Union, Optional
from typing import Literal, Dict, List, Any

from .time_util import Timerange

from .metadata import AnimationMeta
from .metadata import IntroType, OutroType, GroupAnimationType
from .metadata import TextIntro, TextOutro, TextLoopAnim

class Animation:
    """A video/text animation effect"""

    name: str
    """Animation name, defaults to effect name"""
    effect_id: str
    """Internal animation ID from CapCut"""
    animation_type: str
    """Animation type, defined in subclasses"""
    resource_id: str
    """Resource ID from CapCut"""

    start: int
    """Animation offset relative to segment start in microseconds"""
    duration: int
    """Animation duration in microseconds"""

    is_video_animation: bool
    """Whether video animation, defined in subclasses"""

    def __init__(self, animation_meta: AnimationMeta, start: int, duration: int):
        self.name = animation_meta.title
        self.effect_id = animation_meta.effect_id
        self.resource_id = animation_meta.resource_id

        self.start = start
        self.duration = duration

    def export_json(self) -> Dict[str, Any]:
        return {
            "anim_adjust_params": None,
            "platform": "all",
            "panel": "video" if self.is_video_animation else "",
            "material_type": "video" if self.is_video_animation else "sticker",

            "name": self.name,
            "id": self.effect_id,
            "type": self.animation_type,
            "resource_id": self.resource_id,

            "start": self.start,
            "duration": self.duration,
            # Do not export path and request_id
        }

class VideoAnimation(Animation):
    """A video animation effect"""

    animation_type: Literal["in", "out", "group"]

    def __init__(self, animation_type: Union[IntroType, OutroType, GroupAnimationType],
                 start: int, duration: int):
        super().__init__(animation_type.value, start, duration)

        if isinstance(animation_type, IntroType):
            self.animation_type = "in"
        elif isinstance(animation_type, OutroType):
            self.animation_type = "out"
        elif isinstance(animation_type, GroupAnimationType):
            self.animation_type = "group"

        self.is_video_animation = True

class TextAnimation(Animation):
    """A text animation effect"""

    animation_type: Literal["in", "out", "loop"]

    def __init__(self, animation_type: Union[TextIntro, TextOutro, TextLoopAnim],
                 start: int, duration: int):
        super().__init__(animation_type.value, start, duration)

        if isinstance(animation_type, TextIntro):
            self.animation_type = "in"
        elif isinstance(animation_type, TextOutro):
            self.animation_type = "out"
        elif isinstance(animation_type, TextLoopAnim):
            self.animation_type = "loop"

        self.is_video_animation = False

class SegmentAnimations:
    """Series of animations attached to a material
    
    For video: intro, outro, or group; for text: intro, outro, or loop"""

    animation_id: str
    """Global ID for animation series, auto-generated"""

    animations: List[Animation]
    """Animation list"""

    def __init__(self):
        self.animation_id = uuid.uuid4().hex
        self.animations = []

    def get_animation_trange(self, animation_type: Literal["in", "out", "group", "loop"]) -> Optional[Timerange]:
        """Get time range for specified animation type"""
        for animation in self.animations:
            if animation.animation_type == animation_type:
                return Timerange(animation.start, animation.duration)
        return None

    def add_animation(self, animation: Union[VideoAnimation, TextAnimation]) -> None:
        # Do not allow more than one animation of the same type
        if animation.animation_type in [ani.animation_type for ani in self.animations]:
            raise ValueError(f"Segment already has animation of type '{animation.animation_type}'")

        if isinstance(animation, VideoAnimation):
            # Group animation and intro/outro cannot coexist
            if any(ani.animation_type == "group" for ani in self.animations):
                raise ValueError("Segment already has group animation, no other animations allowed")
            if animation.animation_type == "group" and len(self.animations) > 0:
                raise ValueError("Cannot add group animation when segment already has other animations")
        elif isinstance(animation, TextAnimation):
            if any(ani.animation_type == "loop" for ani in self.animations):
                raise ValueError("Segment already has loop animation. To use loop with intro/outro, add intro/outro first.")

        self.animations.append(animation)

    def export_json(self) -> Dict[str, Any]:
        return {
            "id": self.animation_id,
            "type": "sticker_animation",
            "multi_language_current": "none",
            "animations": [animation.export_json() for animation in self.animations]
        }
