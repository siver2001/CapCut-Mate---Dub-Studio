"""Define audio segment and related classes

Contains classes for fade in/out effects, audio effects, etc.
"""

import uuid
from copy import deepcopy

from typing import Optional, Literal, Union
from typing import Dict, List, Any

from .time_util import tim, Timerange
from .segment import MediaSegment
from .local_materials import AudioMaterial
from .keyframe import KeyframeProperty, KeyframeList

from .metadata import EffectParamInstance
from .metadata import AudioSceneEffectType, ToneEffectType, SpeechToSongType

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

class AudioEffect:
    """Audio effect object"""

    name: str
    """Effect name"""
    effect_id: str
    """Global effect ID, auto-generated"""
    resource_id: str
    """Resource ID from CapCut"""

    category_id: Literal["sound_effect", "tone", "speech_to_song"]
    category_name: Literal["Scene Sound", "Tone", "Speech to Song"]
    category_index: Literal[1, 2, 3]

    audio_adjust_params: List[EffectParamInstance]

    def __init__(self, effect_meta: Union[AudioSceneEffectType, ToneEffectType, SpeechToSongType],
                 params: Optional[List[Optional[float]]] = None):
        """Construct an audio effect object based on metadata and parameters (range 0-100)"""

        self.name = effect_meta.value.name
        self.effect_id = uuid.uuid4().hex
        self.resource_id = effect_meta.value.resource_id
        self.audio_adjust_params = []

        if isinstance(effect_meta, AudioSceneEffectType):
            self.category_id = "sound_effect"
            self.category_name = "Scene Sound"
            self.category_index = 1
        elif isinstance(effect_meta, ToneEffectType):
            self.category_id = "tone"
            self.category_name = "Tone"
            self.category_index = 2
        elif isinstance(effect_meta, SpeechToSongType):
            self.category_id = "speech_to_song"
            self.category_name = "Speech to Song"
            self.category_index = 3
        else:
            raise TypeError("Unsupported metadata type %s" % type(effect_meta))

        self.audio_adjust_params = effect_meta.value.parse_params(params)

    def export_json(self) -> Dict[str, Any]:
        return {
            "audio_adjust_params": [param.export_json() for param in self.audio_adjust_params],
            "category_id": self.category_id,
            "category_name": self.category_name,
            "id": self.effect_id,
            "is_ugc": False,
            "name": self.name,
            "production_path": "",
            "resource_id": self.resource_id,
            "speaker_id": "",
            "sub_type": self.category_index,
            "time_range": {"duration": 0, "start": 0},  # Not seemingly used
            "type": "audio_effect"
            # Do not export path and constant_material_id
        }

class AudioSegment(MediaSegment):
    """An audio segment placed on a track"""

    material_instance: AudioMaterial
    """Audio material instance"""

    fade: Optional[AudioFade]
    """Audio fade-in/out effect, can be None
    
    Auto-added to material list when placed on track
    """

    effects: List[AudioEffect]
    """List of audio effects
    
    Auto-added to material list when placed on track
    """

    def __init__(self, material: Union[AudioMaterial, str], target_timerange: Timerange, *,
                 source_timerange: Optional[Timerange] = None, speed: Optional[float] = None, volume: float = 1.0,
                 change_pitch: bool = False):
        """Construct a track segment using specified audio material and time/playback settings

        Args:
            material (`AudioMaterial` or `str`): Material instance or path.
            target_timerange (`Timerange`): Target time range on track.
            source_timerange (`Timerange`, optional): Source material clip range. Defaults to beginning based on `speed` and `target_timerange`.
            speed (`float`, optional): Playback speed. Default is 1.0. If specified with `source_timerange`, overrides `target_timerange` duration.
            volume (`float`, optional): Volume. Default is 1.0.
            change_pitch (`bool`, optional): Whether to follow pitch change with speed. Default is False.

        Raises:
            `ValueError`: Specified or calculated `source_timerange` exceeds material duration.
        """
        if isinstance(material, str):
            material = AudioMaterial(material)

        if source_timerange is not None and speed is not None:
            target_timerange = Timerange(target_timerange.start, round(source_timerange.duration / speed))
        elif source_timerange is not None and speed is None:
            speed = source_timerange.duration / target_timerange.duration
        else:  # source_timerange is None
            speed = speed if speed is not None else 1.0
            source_timerange = Timerange(0, round(target_timerange.duration * speed))

        if source_timerange.end > material.duration:
            raise ValueError(f"Captured material time range {source_timerange} exceeds material duration ({material.duration})")

        super().__init__(material.material_id, source_timerange, target_timerange, speed, volume, change_pitch)

        self.material_instance = deepcopy(material)
        self.fade = None
        self.effects = []

    def add_effect(self, effect_type: Union[AudioSceneEffectType, ToneEffectType, SpeechToSongType],
                   params: Optional[List[Optional[float]]] = None) -> "AudioSegment":
        """Add an audio effect to the segment. Currently 'Speech to Song' may not be auto-recognized.

        Args:
            effect_type (`AudioSceneEffectType` | `ToneEffectType` | `SpeechToSongType`): Effect type. Only one of each category allowed.
            params (`List[Optional[float]]`, optional): Parameters (0-100). 
                Items provided as None use default values. Parameter order depends on enum member annotations.

        Raises:
            `ValueError`: Adding duplicate type, too many parameters, or values out of range.
        """
        if params is not None and len(params) > len(effect_type.value.params):
            raise ValueError("Too many parameters for audio effect %s" % effect_type.value.name)

        effect_inst = AudioEffect(effect_type, params)
        if effect_inst.category_id in [eff.category_id for eff in self.effects]:
            raise ValueError("Segment already has an effect of this category (%s)" % effect_inst.category_name)
        self.effects.append(effect_inst)
        self.extra_material_refs.append(effect_inst.effect_id)

        return self

    def add_fade(self, in_duration: Union[str, int], out_duration: Union[str, int]) -> "AudioSegment":
        """Add fade-in/out effect to the audio segment

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

    def add_keyframe(self, time_offset: int, volume: float) -> "AudioSegment":
        """Create a *volume control* keyframe and add it to the list

        Args:
            time_offset (`int`): Time offset in microseconds
            volume (`float`): Volume value at `time_offset`
        """
        _property = KeyframeProperty.volume
        for kf_list in self.common_keyframes:
            if kf_list.keyframe_property == _property:
                kf_list.add_keyframe(time_offset, volume)
                return self
        kf_list = KeyframeList(_property)
        kf_list.add_keyframe(time_offset, volume)
        self.common_keyframes.append(kf_list)
        return self

    def export_json(self) -> Dict[str, Any]:
        json_dict = super().export_json()
        json_dict.update({
            "clip": None,
            "hdr_settings": None
        })
        return json_dict
