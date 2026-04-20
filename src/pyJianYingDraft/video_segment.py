"""Define video segment and related classes

Contains classes for image adjustment settings, animations, effects, transitions, etc.
"""

import uuid
from copy import deepcopy

from typing import Optional, Literal, Union
from typing import Dict, List, Tuple, Any

from .time_util import tim, Timerange
from .segment import VisualSegment, ClipSettings, AudioFade
from .local_materials import VideoMaterial
from .animation import SegmentAnimations, VideoAnimation

from .metadata import EffectMeta, EffectParamInstance
from .metadata import MaskMeta, MaskType, FilterType, TransitionType
from .metadata import IntroType, OutroType, GroupAnimationType
from .metadata import VideoSceneEffectType, VideoCharacterEffectType
from .metadata.mix_mode_meta import MixModeType

class Mask:
    """Mask object"""

    mask_meta: MaskMeta
    """Mask metadata"""
    global_id: str
    """Mask global ID, auto-generated"""

    center_x: float
    """Mask center X coordinate, in units of half material width"""
    center_y: float
    """Mask center Y coordinate, in units of half material height"""
    width: float
    height: float
    aspect_ratio: float

    rotation: float
    invert: bool
    feather: float
    """Feather degree, 0-1"""
    round_corner: float
    """Round corner for rectangular mask, 0-1"""

    def __init__(self, mask_meta: MaskMeta,
                 cx: float, cy: float, w: float, h: float,
                 ratio: float, rot: float, inv: bool, feather: float, round_corner: float):
        self.mask_meta = mask_meta
        self.global_id = uuid.uuid4().hex

        self.center_x, self.center_y = cx, cy
        self.width, self.height = w, h
        self.aspect_ratio = ratio

        self.rotation = rot
        self.invert = inv
        self.feather = feather
        self.round_corner = round_corner

    def export_json(self) -> Dict[str, Any]:
        return {
            "config": {
                "aspectRatio": self.aspect_ratio,
                "centerX": self.center_x,
                "centerY": self.center_y,
                "feather": self.feather,
                "height": self.height,
                "invert": self.invert,
                "rotation": self.rotation,
                "roundCorner": self.round_corner,
                "width": self.width
            },
            "id": self.global_id,
            "name": self.mask_meta.name,
            "platform": "all",
            "position_info": "",
            "resource_type": self.mask_meta.resource_type,
            "resource_id": self.mask_meta.resource_id,
            "type": "mask"
            # Do not export path field
        }

class VideoEffect:
    """Video effect material"""

    name: str
    """Effect name"""
    global_id: str
    """Effect global ID, auto-generated"""
    effect_id: str
    """Internal effect ID from CapCut"""
    resource_id: str
    """Resource ID from CapCut"""

    effect_type: Literal["video_effect", "face_effect"]
    apply_target_type: Literal[0, 2]
    """Application target type, 0: segment, 2: global"""

    adjust_params: List[EffectParamInstance]

    def __init__(self, effect_meta: Union[VideoSceneEffectType, VideoCharacterEffectType],
                 params: Optional[List[Optional[float]]] = None, *,
                 apply_target_type: Literal[0, 2] = 0):
        """Construct a video effect object based on metadata and parameters (range 0-100)"""

        self.name = effect_meta.value.name
        self.global_id = uuid.uuid4().hex
        self.effect_id = effect_meta.value.effect_id
        self.resource_id = effect_meta.value.resource_id
        self.adjust_params = []

        if isinstance(effect_meta, VideoSceneEffectType):
            self.effect_type = "video_effect"
        elif isinstance(effect_meta, VideoCharacterEffectType):
            self.effect_type = "face_effect"
        else:
            raise TypeError("Invalid effect meta type %s" % type(effect_meta))
        self.apply_target_type = apply_target_type

        self.adjust_params = effect_meta.value.parse_params(params)

    def export_json(self) -> Dict[str, Any]:
        return {
            "adjust_params": [param.export_json() for param in self.adjust_params],
            "apply_target_type": self.apply_target_type,
            "apply_time_range": None,
            "category_id": "",  # Always empty
            "category_name": "",  # Always empty
            "common_keyframes": [],
            "disable_effect_faces": [],
            "effect_id": self.effect_id,
            "formula_id": "",
            "id": self.global_id,
            "name": self.name,
            "platform": "all",
            "render_index": 11000,
            "resource_id": self.resource_id,
            "source_platform": 0,
            "time_range": None,
            "track_render_index": 0,
            "type": self.effect_type,
            "value": 1.0,
            "version": ""
            # Do not export path, request_id, and algorithm_artifact_path fields
        }

class Filter:
    """Filter material"""

    global_id: str
    """Filter global ID, auto-generated"""

    effect_meta: EffectMeta
    """Filter metadata"""
    intensity: float
    """Filter intensity (the only parameter)"""

    apply_target_type: Literal[0, 2]
    """Application target type, 0: segment, 2: global"""

    def __init__(self, meta: EffectMeta, intensity: float, *,
                 apply_target_type: Literal[0, 2] = 0):
        """Construct a filter material object based on metadata and intensity"""

        self.global_id = uuid.uuid4().hex
        self.effect_meta = meta
        self.intensity = intensity
        self.apply_target_type = apply_target_type

    def export_json(self) -> Dict[str, Any]:
        return {
            "adjust_params": [],
            "algorithm_artifact_path": "",
            "apply_target_type": self.apply_target_type,
            "bloom_params": None,
            "category_id": "",  # Always empty
            "category_name": "",  # Always empty
            "color_match_info": {
                "source_feature_path": "",
                "target_feature_path": "",
                "target_image_path": ""
            },
            "effect_id": self.effect_meta.effect_id,
            "enable_skin_tone_correction": False,
            "exclusion_group": [],
            "face_adjust_params": [],
            "formula_id": "",
            "id": self.global_id,
            "intensity_key": "",
            "multi_language_current": "",
            "name": self.effect_meta.name,
            "panel_id": "",
            "platform": "all",
            "resource_id": self.effect_meta.resource_id,
            "source_platform": 1,
            "sub_type": "none",
            "time_range": None,
            "type": "filter",
            "value": self.intensity,
            "version": ""
            # Do not export path and request_id
        }

class Transition:
    """Transition object"""

    name: str
    """Transition name"""
    global_id: str
    """Transition global ID, auto-generated"""
    effect_id: str
    """Internal transition effect ID from CapCut"""
    resource_id: str
    """Resource ID from CapCut"""

    duration: int
    """Transition duration in microseconds"""
    is_overlap: bool
    """Whether to overlap with previous segment"""

    def __init__(self, effect_meta: TransitionType, duration: Optional[int] = None):
        """Construct a transition object based on metadata and duration"""
        self.name = effect_meta.value.name
        self.global_id = uuid.uuid4().hex
        self.effect_id = effect_meta.value.effect_id
        self.resource_id = effect_meta.value.resource_id

        self.duration = duration if duration is not None else effect_meta.value.default_duration
        self.is_overlap = effect_meta.value.is_overlap

    def export_json(self) -> Dict[str, Any]:
        return {
            "category_id": "",  # Always empty
            "category_name": "",  # Always empty
            "duration": self.duration,
            "effect_id": self.effect_id,
            "id": self.global_id,
            "is_overlap": self.is_overlap,
            "name": self.name,
            "platform": "all",
            "resource_id": self.resource_id,
            "type": "transition"
            # Do not export path and request_id fields
        }

class BackgroundFilling:
    """Background filling object"""

    global_id: str
    """Background filling global ID, auto-generated"""
    fill_type: Literal["canvas_blur", "canvas_color"]
    """Background filling type"""
    blur: float
    """Blur intensity, 0-1"""
    color: str
    """Background color, format '#RRGGBBAA'"""

    def __init__(self, fill_type: Literal["canvas_blur", "canvas_color"], blur: float, color: str):
        self.global_id = uuid.uuid4().hex
        self.fill_type = fill_type
        self.blur = blur
        self.color = color

    def export_json(self) -> Dict[str, Any]:
        return {
            "id": self.global_id,
            "type": self.fill_type,
            "blur": self.blur,
            "color": self.color,
            "source_platform": 0,
        }

class MixMode:
    """Mix mode object"""

    global_id: str
    """Mix mode global ID, auto-generated"""

    effect_meta: EffectMeta
    """Mix mode metadata"""

    apply_target_type: Literal[0, 2]
    """Application target type, 0: segment, 2: global
    
    Should always be 0 for mix modes
    """

    def __init__(self, meta: EffectMeta, *,
                 apply_target_type: Literal[0, 2] = 0):
        """Construct a mix mode object based on metadata"""

        self.global_id = uuid.uuid4().hex
        self.effect_meta = meta
        self.apply_target_type = apply_target_type

    def export_json(self) -> Dict[str, Any]:
        return {
            "type": "mix_mode",
            "name": self.effect_meta.name,
            "effect_id": self.effect_meta.effect_id,
            "resource_id": self.effect_meta.resource_id,
            "value": 1.0,
            "apply_target_type": self.apply_target_type,
            "platform": "all",
            "source_platform": 0,
            "category_id": "",
            "category_name": "",
            "sub_type": "none",
            "time_range": None,
            "id": self.global_id
        }


class VideoSegment(VisualSegment):
    """A video/image segment placed on a track"""

    material_instance: VideoMaterial
    """Material instance"""
    material_size: Tuple[int, int]
    """Material size"""

    fade: Optional[AudioFade]
    """Audio fade-in/out effect, can be None
    
    Auto-added to material list when placed on track
    """

    effects: List[VideoEffect]
    """List of effects
    
    Auto-added to material list when placed on track
    """
    filters: List[Filter]
    """List of filters
    
    Auto-added to material list when placed on track
    """
    mix_modes: List[MixMode]
    """List of mix modes
    
    Auto-added to material list when placed on track
    """
    mask: Optional[Mask]
    """Mask instance, can be None
    
    Auto-added to material list when placed on track
    """
    transition: Optional[Transition]
    """Transition instance, can be None
    
    Auto-added to material list when placed on track
    """
    background_filling: Optional[BackgroundFilling]
    """Background filling instance, can be None
    
    Auto-added to material list when placed on track
    """

    def __init__(self, material: Union[VideoMaterial, str], target_timerange: Timerange, *,
                 source_timerange: Optional[Timerange] = None, speed: Optional[float] = None, volume: float = 1.0,
                 change_pitch: bool = False, clip_settings: Optional[ClipSettings] = None):
        """Construct a track segment using specified video/image material and time settings

        Args:
            material (`VideoMaterial` or `str`): Material instance or path. If path, automatically constructs instance (cannot specify `cropSettings` in this case).
            target_timerange (`Timerange`): Target time range on track
            source_timerange (`Timerange`, optional): Source material clip range. Defaults to beginning based on `speed` and `target_timerange`.
            speed (`float`, optional): Playback speed. Default is 1.0. If specified with `source_timerange`, overrides `target_timerange` duration.
            volume (`float`, optional): Volume. Default is 1.0.
            change_pitch (`bool`, optional): Whether to follow pitch change with speed. Default is False.
            clip_settings (`ClipSettings`, optional): Image adjustment settings. Default is no change.

        Raises:
            `ValueError`: Specified or calculated `source_timerange` exceeds material duration.
        """
        if isinstance(material, str):
            material = VideoMaterial(material)

        if source_timerange is not None and speed is not None:
            target_timerange = Timerange(target_timerange.start, round(source_timerange.duration / speed))
        elif source_timerange is not None and speed is None:
            speed = source_timerange.duration / target_timerange.duration
        else:  # source_timerange is None
            speed = speed if speed is not None else 1.0
            source_timerange = Timerange(0, round(target_timerange.duration * speed))

        if source_timerange.end > material.duration:
            raise ValueError(f"Captured material time range {source_timerange} exceeds material duration ({material.duration})")

        super().__init__(material.material_id, source_timerange, target_timerange, speed,
                         volume, change_pitch, clip_settings=clip_settings)

        self.material_instance = deepcopy(material)
        self.material_size = (material.width, material.height)
        self.effects = []
        self.filters = []
        self.mix_modes = []
        self.transition = None
        self.mask = None
        self.background_filling = None
        self.fade = None

    def add_animation(self, animation_type: Union[IntroType, OutroType, GroupAnimationType],
                      duration: Optional[Union[int, str]] = None) -> "VideoSegment":
        """Add intro/outro/group animation to the segment's animation list

        Args:
            animation_type (`IntroType`, `OutroType`, or `GroupAnimationType`): Animation type
            duration (`int` or `str`, optional): Animation duration in microseconds. Can be time string parsed via `tim()`.
                If not specified, uses default value from animation type. Theoretically only applicable to intro and outro.
        """
        if duration is not None:
            duration = tim(duration)
        if isinstance(animation_type, IntroType):
            start = 0
            duration = duration or animation_type.value.duration
        elif isinstance(animation_type, OutroType):
            duration = duration or animation_type.value.duration
            start = self.target_timerange.duration - duration
        elif isinstance(animation_type, GroupAnimationType):
            start = 0
            duration = duration or self.target_timerange.duration
        else:
            raise TypeError("Invalid animation type %s" % type(animation_type))

        if self.animations_instance is None:
            self.animations_instance = SegmentAnimations()
            self.extra_material_refs.append(self.animations_instance.animation_id)

        self.animations_instance.add_animation(VideoAnimation(animation_type, start, duration))

        return self

    def add_effect(self, effect_type: Union[VideoSceneEffectType, VideoCharacterEffectType],
                   params: Optional[List[Optional[float]]] = None) -> "VideoSegment":
        """Add an effect to the segment

        Args:
            effect_type (`VideoSceneEffectType` or `VideoCharacterEffectType`): Effect type
            params (`List[Optional[float]]`, optional): Effect parameters list (0-100). 
                Items provided as None use default values. Parameter order depends on enum member annotations.

        Raises:
            `ValueError`: Parameter count exceeds limit or values out of range.
        """
        if params is not None and len(params) > len(effect_type.value.params):
            raise ValueError("Too many parameters for audio effect %s" % effect_type.value.name)

        effect_inst = VideoEffect(effect_type, params)
        self.effects.append(effect_inst)
        self.extra_material_refs.append(effect_inst.global_id)

        return self

    def add_fade(self, in_duration: Union[str, int], out_duration: Union[str, int]) -> "VideoSegment":
        """Add audio fade-in/out effect to video segment (valid only for segments with audio)

        Args:
            in_duration (`int` or `str`): Fade-in duration in microseconds (or time string)
            out_duration (`int` or `str`): Fade-out duration in microseconds (or time string)

        Raises:
            `ValueError`: Segment already has fade effects
        """
        if self.fade is not None:
            raise ValueError("Segment already has fade effects")

        if isinstance(in_duration, str): in_duration = tim(in_duration)
        if isinstance(out_duration, str): out_duration = tim(out_duration)

        self.fade = AudioFade(in_duration, out_duration)
        self.extra_material_refs.append(self.fade.fade_id)

        return self

    def add_filter(self, filter_type: FilterType, intensity: float = 100.0) -> "VideoSegment":
        """Add a filter to the video segment

        Args:
            filter_type (`FilterType`): Filter type
            intensity (`float`, optional): Filter intensity (0-100), default is 100.
        """
        filter_inst = Filter(filter_type.value, intensity / 100.0)  # Convert to 0~1 range
        self.filters.append(filter_inst)
        self.extra_material_refs.append(filter_inst.global_id)

        return self

    def set_mix_mode(self, mode: MixModeType) -> "VideoSegment":
        """Set mix mode for the video segment

        Args:
            mode (`MixModeType`): Mix mode type
        """
        mix_mode_inst = MixMode(mode.value)
        self.mix_modes.append(mix_mode_inst)
        self.extra_material_refs.append(mix_mode_inst.global_id)

        return self

    def add_mask(self, mask_type: MaskType, *, center_x: float = 0.0, center_y: float = 0.0, size: float = 0.5,
                 rotation: float = 0.0, feather: float = 0.0, invert: bool = False,
                 rect_width: Optional[float] = None, round_corner: Optional[float] = None) -> "VideoSegment":
        """Add a mask to the video segment

        Args:
            mask_type (`MaskType`): Mask type
            center_x (`float`, optional): Center point X (pixels), default is material center
            center_y (`float`, optional): Center point Y (pixels), default is material center
            size (`float`, optional): Primary size (visible height/diameter/etc.) as ratio of material height, default 0.5
            rotation (`float`, optional): Clockwise rotation angle, default 0
            feather (`float`, optional): Feather parameter (0-100), default 0
            invert (`bool`, optional): Whether to invert the mask, default False
            rect_width (`float`, optional): Width for rectangular mask (ratio of material width), defaults to `size`
            round_corner (`float`, optional): Round corner for rectangular mask (0-100), default 0

        Raises:
            `ValueError`: Trying to add multiple masks or incorrect setting for `rect_width`/`round_corner`
        """

        if self.mask is not None:
            raise ValueError("Segment already has a mask")
        if (rect_width is not None or round_corner is not None) and mask_type != MaskType.Rectangle:
            raise ValueError("`rect_width` and `round_corner` can only be set for rectangular masks")
        if rect_width is None and mask_type == MaskType.Rectangle:
            rect_width = size
        if round_corner is None:
            round_corner = 0

        width = rect_width or size * self.material_size[1] * mask_type.value.default_aspect_ratio / self.material_size[0]
        self.mask = Mask(mask_type.value, center_x / (self.material_size[0] / 2), center_y / (self.material_size[1] / 2),
                         w=width, h=size, ratio=mask_type.value.default_aspect_ratio,
                         rot=rotation, inv=invert, feather=feather/100, round_corner=round_corner/100)
        self.extra_material_refs.append(self.mask.global_id)
        return self

    def add_transition(self, transition_type: TransitionType, *, duration: Optional[Union[int, str]] = None) -> "VideoSegment":
        """Add transition to video segment. Note: Transition should be added to the PREVIOUS segment.

        Args:
            transition_type (`TransitionType`): Transition type
            duration (`int` or `str`, optional): Transition duration in microseconds (or time string).

        Raises:
            `ValueError`: Trying to add multiple transitions.
        """
        if self.transition is not None:
            raise ValueError("Segment already has a transition")
        if isinstance(duration, str): duration = tim(duration)

        self.transition = Transition(transition_type, duration)
        self.extra_material_refs.append(self.transition.global_id)
        return self

    def add_background_filling(self, fill_type: Literal["blur", "color"], blur: float = 0.0625, color: str = "#00000000") -> "VideoSegment":
        """Add background filling to video segment

        Note: Background filling only affects segments on the bottom-most video track.

        Args:
            fill_type (`blur` or `color`): Filling type
            blur (`float`, optional): Blur intensity (0.0-1.0). Four levels in CapCut are 0.0625, 0.375, 0.75, 1.0. Default 0.0625.
            color (`str`, optional): Filling color, format '#RRGGBBAA'.

        Raises:
            `ValueError`: Segment already has background filling or `fill_type` is invalid.
        """
        if self.background_filling is not None:
            raise ValueError("Segment already has background filling")

        if fill_type == "blur":
            self.background_filling = BackgroundFilling("canvas_blur", blur, color)
        elif fill_type == "color":
            self.background_filling = BackgroundFilling("canvas_color", blur, color)
        else:
            raise ValueError(f"Invalid background filling type {fill_type}")

        self.extra_material_refs.append(self.background_filling.global_id)
        return self

    def export_json(self) -> Dict[str, Any]:
        json_dict = super().export_json()
        json_dict.update({
            "hdr_settings": {"intensity": 1.0, "mode": 1, "nits": 1000},
        })
        return json_dict

class StickerSegment(VisualSegment):
    """A sticker segment placed on a track"""

    resource_id: str
    """Sticker resource ID"""

    def __init__(self, resource_id: str, target_timerange: Timerange, *, clip_settings: Optional[ClipSettings] = None):
        """Construct a sticker segment using resource_id and time settings

        Args:
            resource_id (`str`): Sticker resource_id, can be obtained via `ScriptFile.inspect_material`
            target_timerange (`Timerange`): Target time range on track
            clip_settings (`ClipSettings`, optional): Image adjustment settings
        """
        super().__init__(uuid.uuid4().hex, None, target_timerange, 1.0, 1.0, False, clip_settings=clip_settings)
        self.resource_id = resource_id

    def export_material(self) -> Dict[str, Any]:
        """Create a minimal sticker material object"""
        return {
            "id": self.material_id,
            "resource_id": self.resource_id,
            "sticker_id": self.resource_id,
            "source_platform": 1,
            "type": "sticker",
        }
