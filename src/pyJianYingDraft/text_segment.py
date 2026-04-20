"""Define text segment and related classes"""

import json
import uuid
from copy import deepcopy

from typing import Dict, Tuple, Any, List
from typing import Union, Optional, Literal

from .time_util import Timerange, tim
from .segment import ClipSettings, VisualSegment
from .animation import SegmentAnimations, TextAnimation

from .metadata import FontType, EffectMeta
from .metadata import TextIntro, TextOutro, TextLoopAnim

class TextStyle:
    """Font style class"""

    size: float
    """Font size"""

    bold: bool
    """Whether bold"""
    italic: bool
    """Whether italic"""
    underline: bool
    """Whether underlined"""

    color: Tuple[float, float, float]
    """Font color, RGB triplet, range [0, 1]"""
    alpha: float
    """Font opacity"""

    align: Literal[0, 1, 2]
    """Alignment"""
    vertical: bool
    """Whether vertical text"""

    letter_spacing: int
    """Letter spacing"""
    line_spacing: int
    """Line spacing"""

    auto_wrapping: bool
    """Whether auto-wrap"""
    max_line_width: float
    """Max line width, range [0, 1]"""

    def __init__(self, *, size: float = 8.0, bold: bool = False, italic: bool = False, underline: bool = False,
                 color: Tuple[float, float, float] = (1.0, 1.0, 1.0), alpha: float = 1.0,
                 align: Literal[0, 1, 2] = 0, vertical: bool = False,
                 letter_spacing: int = 0, line_spacing: int = 0,
                 auto_wrapping: bool = False, max_line_width: float = 0.82):
        """
        Args:
            size (`float`, optional): Font size. Default 8.0.
            bold (`bool`, optional): Whether bold. Default False.
            italic (`bool`, optional): Whether italic. Default False.
            underline (`bool`, optional): Whether underlined. Default False.
            color (`Tuple[float, float, float]`, optional): Font color, RGB triplet [0, 1]. Default white.
            alpha (`float`, optional): Font opacity [0, 1]. Default 1.0 (opaque).
            align (`int`, optional): Alignment. 0: Left, 1: Center, 2: Right. Default 0.
            vertical (`bool`, optional): Whether vertical text. Default False.
            letter_spacing (`int`, optional): Letter spacing, consistent with CapCut. Default 0.
            line_spacing (`int`, optional): Line spacing, consistent with CapCut. Default 0.
            auto_wrapping (`bool`, optional): Whether auto-wrap. Default False.
            max_line_width (`float`, optional): Max line width as ratio of screen width [0, 1]. Default 0.82.
        """
        self.size = size
        self.bold = bold
        self.italic = italic
        self.underline = underline

        self.color = color
        self.alpha = alpha

        self.align = align
        self.vertical = vertical

        self.letter_spacing = letter_spacing
        self.line_spacing = line_spacing

        self.auto_wrapping = auto_wrapping
        self.max_line_width = max_line_width

class TextBorder:
    """Text border parameters"""

    alpha: float
    """Border opacity"""
    color: Tuple[float, float, float]
    """Border color, RGB triplet [0, 1]"""
    width: float
    """Border width"""

    def __init__(self, *, alpha: float = 1.0, color: Tuple[float, float, float] = (0.0, 0.0, 0.0), width: float = 40.0):
        """
        Args:
            alpha (`float`, optional): Border opacity [0, 1]. Default 1.0.
            color (`Tuple[float, float, float]`, optional): Border color, RGB triplet [0, 1]. Default black.
            width (`float`, optional): Border width, consistent with CapCut [0, 100]. Default 40.0.
        """
        self.alpha = alpha
        self.color = color
        self.width = width / 100.0 * 0.2  # This mapping might not be perfectly accurate

    def export_json(self) -> Dict[str, Any]:
        """Export JSON data, placed in styles of material content"""
        return {
            "content": {
                "solid": {
                    "alpha": self.alpha,
                    "color": list(self.color),
                }
            },
            "width": self.width
        }

class TextBackground:
    """Text background parameters"""

    style: Literal[1, 2]
    """Background style"""

    alpha: float
    """Background opacity"""
    color: str
    """Background color, format '#RRGGBB'"""
    round_radius: float
    """Background round radius"""
    height: float
    """Background height"""
    width: float
    """Background width"""
    horizontal_offset: float
    """Background horizontal offset"""
    vertical_offset: float
    """Background vertical offset"""

    def __init__(self, *, color: str, style: Literal[1, 2] = 1, alpha: float = 1.0, round_radius: float = 0.0,
                 height: float = 0.14, width: float = 0.14,
                 horizontal_offset: float = 0.5, vertical_offset: float = 0.5):
        """
        Args:
            color (`str`): Background color, format '#RRGGBB'
            style (`int`, optional): Background style, 1 and 2 correspond to CapCut styles. Default 1.
            alpha (`float`, optional): Background opacity [0, 1]. Default 1.0.
            round_radius (`float`, optional): Background round radius [0, 1]. Default 0.0.
            height (`float`, optional): Background height [0, 1]. Default 0.14.
            width (`float`, optional): Background width [0, 1]. Default 0.14.
            horizontal_offset (`float`, optional): Background horizontal offset [0, 1]. Default 0.5.
            vertical_offset (`float`, optional): Background vertical offset [0, 1]. Default 0.5.
        """
        self.style = style

        self.alpha = alpha
        self.color = color
        self.round_radius = round_radius
        self.height = height
        self.width = width
        self.horizontal_offset = horizontal_offset * 2 - 1
        self.vertical_offset = vertical_offset * 2 - 1

    def export_json(self) -> Dict[str, Any]:
        """Generate sub-JSON data, merged into TextSegment when exported"""
        return {
            "background_style": self.style,
            "background_color": self.color,
            "background_alpha": self.alpha,
            "background_round_radius": self.round_radius,
            "background_height": self.height,
            "background_width": self.width,
            "background_horizontal_offset": self.horizontal_offset,
            "background_vertical_offset": self.vertical_offset,
        }

class TextBubble:
    """Text bubble material, essentially similar to filter material"""

    global_id: str
    """Bubble global ID, auto-generated"""

    effect_id: str
    resource_id: str

    def __init__(self, effect_id: str, resource_id: str):
        self.global_id = uuid.uuid4().hex
        self.effect_id = effect_id
        self.resource_id = resource_id

    def export_json(self) -> Dict[str, Any]:
        return {
            "apply_target_type": 0,
            "effect_id": self.effect_id,
            "id": self.global_id,
            "resource_id": self.resource_id,
            "type": "text_shape",
            "value": 1.0,
            # Do not export path and request_id
        }

class TextEffect(TextBubble):
    """Text effect material, essentially similar to filter material"""

    def export_json(self) -> Dict[str, Any]:
        ret = super().export_json()
        ret["type"] = "text_effect"
        ret["source_platform"] = 1
        return ret

class TextShadow:
    """Text shadow parameters"""

    alpha: float
    """Shadow opacity, range [0, 1]"""
    color: Tuple[float, float, float]
    """Shadow color, RGB triplet [0, 1]"""
    diffuse: float
    """Shadow diffuse degree, range [0, 100]"""
    distance: float
    """Shadow distance, range [0, 100]"""
    angle: float
    """Shadow angle, range [-180, 180]"""

    def __init__(self, *, alpha: float = 1.0, color: Tuple[float, float, float] = (0.0, 0.0, 0.0),
                 diffuse: float = 15.0, distance: float = 5.0, angle: float = -45.0):
        """
        Args:
            alpha (`float`, optional): Shadow opacity [0, 1]. Default 1.0.
            color (`Tuple[float, float, float]`, optional): Shadow color, RGB triplet [0, 1]. Default black.
            diffuse (`float`, optional): Shadow diffuse [0, 100]. Default 15.0.
            distance (`float`, optional): Shadow distance [0, 100]. Default 5.0.
            angle (`float`, optional): Shadow angle [-180, 180]. Default -45.0.
        """
        self.alpha = alpha
        self.color = color
        self.diffuse = diffuse
        self.distance = distance
        self.angle = angle

    def export_json(self) -> Dict[str, Any]:
        return {
            "diffuse": self.diffuse / 100.0 / 6,  # /6 is CapCut's built-in mapping
            "alpha": self.alpha,
            "distance": self.distance,
            "content": {
                "solid": {
                    "color": list(self.color),
                }
            },
            "angle": self.angle
        }

class TextSegment(VisualSegment):
    """Text segment class, currently supports basic font styles"""

    text: str
    """Text content"""
    font: Optional[EffectMeta]
    """Font type"""
    style: TextStyle
    """Font style"""

    border: Optional[TextBorder]
    """Text border parameters, None means no border"""
    background: Optional[TextBackground]
    """Text background parameters, None means no background"""
    shadow: Optional[TextShadow]
    """Text shadow parameters, None means no shadow"""

    bubble: Optional[TextBubble]
    """Text bubble effect, added to material list when placed on track"""
    effect: Optional[TextEffect]
    """Text effect, added to material list when placed on track. Currently only some effects supported."""
    extra_styles: List[Dict[str, Any]]
    """Extra text styles, used for keyword highlighting, etc."""

    def __init__(self, text: str, timerange: Timerange, *,
                 font: Optional[FontType] = None,
                 style: Optional[TextStyle] = None, clip_settings: Optional[ClipSettings] = None,
                 border: Optional[TextBorder] = None, background: Optional[TextBackground] = None,
                 shadow: Optional[TextShadow] = None):
        """Create text segment and specify time, font style, and image adjustment

        Args:
            text (`str`): Text content
            timerange (`Timerange`): Time range on track
            font (`FontType`, optional): Font type. Default is system font.
            style (`TextStyle`, optional): Font style including size, color, alignment, etc.
            clip_settings (`ClipSettings`, optional): Image adjustment settings. Default is no change.
            border (`TextBorder`, optional): Border parameters. Default is no border.
            background (`TextBackground`, optional): Background parameters. Default is no background.
            shadow (`TextShadow`, optional): Shadow parameters. Default is no shadow.
        """
        super().__init__(uuid.uuid4().hex, None, timerange, 1.0, 1.0, False, clip_settings=clip_settings)

        self.text = text
        self.font = font.value if font else None
        self.style = style or TextStyle()
        self.border = border
        self.background = background
        self.shadow = shadow

        self.bubble = None
        self.effect = None
        self.extra_styles = []

    @classmethod
    def create_from_template(cls, text: str, timerange: Timerange, template: "TextSegment") -> "TextSegment":
        """Create a new text segment from a template and specify its content"""
        new_segment = cls(text, timerange, style=deepcopy(template.style), clip_settings=deepcopy(template.clip_settings),
                          border=deepcopy(template.border), background=deepcopy(template.background),
                          shadow=deepcopy(template.shadow))
        new_segment.font = deepcopy(template.font)

        # Handle animations etc.
        if template.animations_instance:
            new_segment.animations_instance = deepcopy(template.animations_instance)
            new_segment.animations_instance.animation_id = uuid.uuid4().hex
            new_segment.extra_material_refs.append(new_segment.animations_instance.animation_id)
        if template.bubble:
            new_segment.add_bubble(template.bubble.effect_id, template.bubble.resource_id)
        if template.effect:
            new_segment.add_effect(template.effect.effect_id)

        return new_segment

    def add_animation(self, animation_type: Union[TextIntro, TextOutro, TextLoopAnim],
                      duration: Union[str, float, None] = None) -> "TextSegment":
        """Add intro/outro/loop animation to the segment. Intro/outro duration can be set, loop animation auto-fills the rest.

        Note: To use loop with intro/outro, **add intro/outro first, then loop**.

        Args:
            animation_type (`TextIntro`, `TextOutro` or `TextLoopAnim`): Animation type.
            duration (`str` or `float`, optional): Duration in microseconds (intro/outro only).
                If string, parsed via `tim()`. Default uses animation's defined duration.
        """
        if duration is None:
            duration = animation_type.value.duration
        duration = min(tim(duration), self.target_timerange.duration)

        if isinstance(animation_type, TextIntro):
            start = 0
        elif isinstance(animation_type, TextOutro):
            start = self.target_timerange.duration - duration
        elif isinstance(animation_type, TextLoopAnim):
            intro_trange = self.animations_instance and self.animations_instance.get_animation_trange("in")
            outro_trange = self.animations_instance and self.animations_instance.get_animation_trange("out")
            start = intro_trange.start if intro_trange else 0
            duration = self.target_timerange.duration - start - (outro_trange.duration if outro_trange else 0)
        else:
            raise TypeError("Invalid animation type %s" % type(animation_type))

        if self.animations_instance is None:
            self.animations_instance = SegmentAnimations()
            self.extra_material_refs.append(self.animations_instance.animation_id)

        self.animations_instance.add_animation(TextAnimation(animation_type, start, duration))

        return self

    def add_bubble(self, effect_id: str, resource_id: str) -> "TextSegment":
        """Add bubble effect based on material info (obtainable via `ScriptFile.inspect_material`)

        Args:
            effect_id (`str`): Bubble effect_id
            resource_id (`str`): Bubble resource_id
        """
        self.bubble = TextBubble(effect_id, resource_id)
        self.extra_material_refs.append(self.bubble.global_id)
        return self

    def add_effect(self, effect_id: str) -> "TextSegment":
        """Add text effect based on material info (obtainable via `ScriptFile.inspect_material`)

        Args:
            effect_id (`str`): Effect_id (also resource_id)
        """
        self.effect = TextEffect(effect_id, effect_id)
        self.extra_material_refs.append(self.effect.global_id)
        return self

    def export_material(self) -> Dict[str, Any]:
        """Material associated with this text segment, no separate TextMaterial class needed"""
        check_flag = 7
        # Flag for combining various effects
        if self.border:
            check_flag |= 8
        if self.background:
            check_flag |= 16
        if self.shadow:
            check_flag |= 32

        # Create base style
        base_style = {
            "fill": {
                "alpha": 1.0,
                "content": {
                    "render_type": "solid",
                    "solid": {
                        "alpha": 1.0,
                        "color": list(self.style.color)
                    }
                }
            },
            "range": [0, len(self.text.encode('utf-16-le'))],
            "size": self.style.size,
            "bold": self.style.bold,
            "italic": self.style.italic,
            "underline": self.style.underline,
            "strokes": [self.border.export_json()] if self.border else []
        }
        
        # Combine base style and extra styles
        styles = [base_style] + self.extra_styles
        
        content_json = {
            "styles": styles,
            "text": self.text
        }
        if self.font:
            content_json["styles"][0]["font"] = {
                "id": self.font.resource_id,
                "path": "D:"  # No actual font file placed here
            }
        if self.effect:
            content_json["styles"][0]["effectStyle"] = {
                "id": self.effect.effect_id,
                "path": "C:"  # No actual material file placed here
            }
        if self.shadow:
            content_json["styles"][0]["shadows"] = [self.shadow.export_json()]

        ret = {
            "id": self.material_id,
            "content": json.dumps(content_json, ensure_ascii=False),

            "typesetting": int(self.style.vertical),
            "alignment": self.style.align,
            "letter_spacing": self.style.letter_spacing * 0.05,
            "line_spacing": 0.02 + self.style.line_spacing * 0.05,

            "line_feed": 1,
            "line_max_width": self.style.max_line_width,
            "force_apply_line_max_width": False,

            "check_flag": check_flag,

            "type": "subtitle" if self.style.auto_wrapping else "text",

            # Blend (+4)
            "global_alpha": self.style.alpha,

            # Glow (+64), attributes recorded by extra_material_refs
        }

        if self.background:
            ret.update(self.background.export_json())

        return ret
