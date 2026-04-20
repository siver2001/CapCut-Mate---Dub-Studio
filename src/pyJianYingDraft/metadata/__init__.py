"""Records metadata for various effects, audio effects, filters, etc.

Audio-related metadata updated: 2024
Other metadata updated: 2026-03
"""
from .effect_meta import EffectMeta, EffectParamInstance
from .effect_meta import AnimationMeta

# Video Effects
from .video_scene_effect import VideoSceneEffectType
from .video_character_effect import VideoCharacterEffectType

# Video Animation
from .video_intro import IntroType
from .video_outro import OutroType
from .video_group_animation import GroupAnimationType
# Audio Effects
from .audio_scene_effect import AudioSceneEffectType
from .tone_effect import ToneEffectType
from .speech_to_song import SpeechToSongType

# Text Animation
from .text_intro import TextIntro
from .text_outro import TextOutro
from .text_loop import TextLoopAnim

# Other
from .font_meta import FontType
from .mask_meta import MaskType, MaskMeta
from .filter_meta import FilterType
from .transition_meta import TransitionType
from .mix_mode_meta import MixModeType

__all__ = [
    "AnimationMeta",
    "EffectMeta",
    "EffectParamInstance",
    "MaskType",
    "MaskMeta",
    "FilterType",
    "FontType",
    "TransitionType",
    "MixModeType",
    "IntroType",
    "OutroType",
    "GroupAnimationType",
    "TextIntro",
    "TextOutro",
    "TextLoopAnim",
    "AudioSceneEffectType",
    "ToneEffectType",
    "SpeechToSongType",
    "VideoSceneEffectType",
    "VideoCharacterEffectType"
]
