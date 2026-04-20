import os
import json
import math
from copy import deepcopy

from typing import Optional, Literal, Union, overload
from typing import Type, Dict, List, Any

from . import util
from . import assets
from . import exceptions
from .template_mode import ImportedTrack, EditableTrack, ImportedMediaTrack, ImportedTextTrack, ShrinkMode, ExtendMode, import_track
from .time_util import Timerange, tim, srt_tstamp
from .local_materials import VideoMaterial, AudioMaterial
from .segment import BaseSegment, Speed, ClipSettings
from .audio_segment import AudioSegment, AudioFade, AudioEffect
from .video_segment import VideoSegment, StickerSegment, SegmentAnimations, VideoEffect, Transition, Filter, BackgroundFilling, MixMode
from .effect_segment import EffectSegment, FilterSegment
from .text_segment import TextSegment, TextStyle, TextBubble
from .track import TrackType, BaseTrack, Track

from .metadata import VideoSceneEffectType, VideoCharacterEffectType, FilterType

class ScriptMaterial:
    """Material information part in the draft file"""

    audios: List[AudioMaterial]
    """List of audio materials"""
    videos: List[VideoMaterial]
    """List of video materials"""
    stickers: List[Dict[str, Any]]
    """List of sticker materials"""
    texts: List[Dict[str, Any]]
    """List of text materials"""

    audio_effects: List[AudioEffect]
    """List of audio effects"""
    audio_fades: List[AudioFade]
    """List of audio fade-in/out effects"""
    animations: List[SegmentAnimations]
    """List of animation materials"""
    video_effects: List[VideoEffect]
    """List of video effects"""

    speeds: List[Speed]
    """List of speed change settings"""
    masks: List[Dict[str, Any]]
    """List of masks"""
    transitions: List[Transition]
    """List of transition effects"""
    filters: List[Union[Filter, TextBubble]]
    """List of filters/text bubbles, exported to `effects`"""
    mix_modes: List[MixMode]
    """List of blend modes, exported to `effects`"""
    canvases: List[BackgroundFilling]
    """List of background fillings"""

    def __init__(self):
        self.audios = []
        self.videos = []
        self.stickers = []
        self.texts = []

        self.audio_effects = []
        self.audio_fades = []
        self.animations = []
        self.video_effects = []

        self.speeds = []
        self.masks = []
        self.transitions = []
        self.filters = []
        self.mix_modes = []
        self.canvases = []

    @overload
    def __contains__(self, item: Union[VideoMaterial, AudioMaterial]) -> bool: ...
    @overload
    def __contains__(self, item: Union[AudioFade, AudioEffect]) -> bool: ...
    @overload
    def __contains__(self, item: Union[SegmentAnimations, VideoEffect, Transition, Filter]) -> bool: ...

    def __contains__(self, item) -> bool:
        if isinstance(item, VideoMaterial):
            return item.material_id in [video.material_id for video in self.videos]
        elif isinstance(item, AudioMaterial):
            return item.material_id in [audio.material_id for audio in self.audios]
        elif isinstance(item, AudioFade):
            return item.fade_id in [fade.fade_id for fade in self.audio_fades]
        elif isinstance(item, AudioEffect):
            return item.effect_id in [effect.effect_id for effect in self.audio_effects]
        elif isinstance(item, SegmentAnimations):
            return item.animation_id in [ani.animation_id for ani in self.animations]
        elif isinstance(item, VideoEffect):
            return item.global_id in [effect.global_id for effect in self.video_effects]
        elif isinstance(item, Transition):
            return item.global_id in [transition.global_id for transition in self.transitions]
        elif isinstance(item, Filter):
            return item.global_id in [filter_.global_id for filter_ in self.filters]
        elif isinstance(item, MixMode):
            return item.global_id in [mix_mode.global_id for mix_mode in self.mix_modes]
        else:
            raise TypeError("Invalid argument type '%s'" % type(item))

    def export_json(self) -> Dict[str, List[Any]]:
        return {
            "ai_translates": [],
            "audio_balances": [],
            "audio_effects": [effect.export_json() for effect in self.audio_effects],
            "audio_fades": [fade.export_json() for fade in self.audio_fades],
            "audio_track_indexes": [],
            "audios": [audio.export_json() for audio in self.audios],
            "beats": [],
            "canvases": [canvas.export_json() for canvas in self.canvases],
            "chromas": [],
            "color_curves": [],
            "digital_humans": [],
            "drafts": [],
            "effects": [_filter.export_json() for _filter in self.filters] + [mix_mode.export_json() for mix_mode in self.mix_modes],
            "flowers": [],
            "green_screens": [],
            "handwrites": [],
            "hsl": [],
            "images": [],
            "log_color_wheels": [],
            "loudnesses": [],
            "manual_deformations": [],
            "masks": self.masks,
            "material_animations": [ani.export_json() for ani in self.animations],
            "material_colors": [],
            "multi_language_refs": [],
            "placeholders": [],
            "plugin_effects": [],
            "primary_color_wheels": [],
            "realtime_denoises": [],
            "shapes": [],
            "smart_crops": [],
            "smart_relights": [],
            "sound_channel_mappings": [],
            "speeds": [spd.export_json() for spd in self.speeds],
            "stickers": self.stickers,
            "tail_leaders": [],
            "text_templates": [],
            "texts": self.texts,
            "time_marks": [],
            "transitions": [transition.export_json() for transition in self.transitions],
            "video_effects": [effect.export_json() for effect in self.video_effects],
            "video_trackings": [],
            "videos": [video.export_json() for video in self.videos],
            "vocal_beautifys": [],
            "vocal_separations": []
        }

class ScriptFile:
    """CapCut draft file, most interfaces are defined here"""

    save_path: Optional[str]
    """Save path of the draft file, valid only in template mode"""
    content: Dict[str, Any]
    """Content of the draft file"""

    width: int
    """Video width in pixels"""
    height: int
    """Video height in pixels"""
    fps: int
    """Video frame rate"""
    duration: int
    """Total video duration in microseconds"""

    maintrack_adsorb: bool
    """Whether to enable main track magnetic absorption"""

    materials: ScriptMaterial
    """Material information part in the draft file"""
    tracks: Dict[str, Track]
    """Track information"""

    imported_materials: Dict[str, List[Dict[str, Any]]]
    """Imported material information"""
    imported_tracks: List[ImportedTrack]
    """Imported track information"""

    dual_file_compatibility: bool
    """Dual file compatibility mode, saves both draft_content.json and draft_info.json when enabled"""

    def __init__(self, width: int, height: int, fps: int, maintrack_adsorb: bool):
        """**Recommended to use `DraftFolder.create_draft()` instead of this method**

        Args:
            width (int): Video width in pixels
            height (int): Video height in pixels
            fps (int): Video frame rate
            maintrack_adsorb (bool): Whether to enable main track magnetic absorption
        """
        self.save_path = None

        self.width = width
        self.height = height
        self.fps = fps
        self.duration = 0
        self.maintrack_adsorb = maintrack_adsorb

        self.materials = ScriptMaterial()
        self.tracks = {}

        self.imported_materials = {}
        self.imported_tracks = []

        self.dual_file_compatibility = True  # Enable dual file compatibility mode

        with open(assets.get_asset_path('DRAFT_CONTENT_TEMPLATE'), "r", encoding="utf-8") as f:
            self.content = json.load(f)

    @staticmethod
    def load_template(json_path: str) -> "ScriptFile":
        """Load draft template from JSON file

        Args:
            json_path (str): Path to JSON file

        Raises:
            `FileNotFoundError`: JSON file does not exist
        """
        obj = ScriptFile(**util.provide_ctor_defaults(ScriptFile))
        obj.save_path = json_path
        if not os.path.exists(json_path):
            raise FileNotFoundError("JSON file '%s' does not exist" % json_path)
        with open(json_path, "r", encoding="utf-8") as f:
            obj.content = json.load(f)

        util.assign_attr_with_json(obj, ["fps", "duration"], obj.content)
        util.assign_attr_with_json(obj, ["maintrack_adsorb"], obj.content["config"])
        util.assign_attr_with_json(obj, ["width", "height"], obj.content["canvas_config"])

        obj.imported_materials = deepcopy(obj.content["materials"])
        obj.imported_tracks = [import_track(track_data) for track_data in obj.content["tracks"]]

        return obj

    def add_material(self, material: Union[VideoMaterial, AudioMaterial]) -> "ScriptFile":
        """Add a material to the draft file"""
        if material in self.materials:  # Material already exists
            return self
        if isinstance(material, VideoMaterial):
            self.materials.videos.append(material)
        elif isinstance(material, AudioMaterial):
            self.materials.audios.append(material)
        else:
            raise TypeError("Invalid material type: '%s'" % type(material))
        return self

    def add_track(self, track_type: TrackType, track_name: Optional[str] = None, *,
                  mute: bool = False,
                  relative_index: int = 0, absolute_index: Optional[int] = None) -> "ScriptFile":
        """Add a track of specified type and name to the draft file, with custom track hierarchy.

        Note: Video segments on the main video track (bottom-most video track) must start from 0s, 
        otherwise they will be forced to align to 0s by CapCut.

        To avoid confusion, omitting the name is only allowed when creating the first track of the same type.

        Args:
            track_type (TrackType): Track type
            track_name (str, optional): Track name. Omissible only for the first track of the same type.
            mute (bool, optional): Whether the track is muted. Default is False.
            relative_index (int, optional): Relative layer position (within tracks of same type), 
                                           higher is closer to foreground. Default is 0.
            absolute_index (int, optional): Absolute layer position, higher is closer to foreground. 
                                           This directly overrides the `render_index` property. 
                                           Cannot be used with `relative_index`.

        Raises:
            `NameError`: Track of same type exists and name is not specified, or track with same name exists.
        """

        if track_name is None:
            if track_type in [track.track_type for track in self.tracks.values()]:
                raise NameError("Track of type '%s' already exists, please specify a name for the new track to avoid confusion" % track_type)
            track_name = track_type.name
        if track_name in [track.name for track in self.tracks.values()]:
            raise NameError("Track named '%s' already exists" % track_name)

        render_index = track_type.value.render_index + relative_index
        if absolute_index is not None:
            render_index = absolute_index

        self.tracks[track_name] = Track(track_type, track_name, render_index, mute)
        return self

    def _get_track(self, segment_type: Type[BaseSegment], track_name: Optional[str]) -> Track:
        # Specified track name
        if track_name is not None:
            if track_name not in self.tracks:
                raise NameError("Track named '%s' does not exist" % track_name)
            return self.tracks[track_name]
        # Find unique track of same type
        count = sum([1 for track in self.tracks.values() if track.accept_segment_type == segment_type])
        if count == 0: raise NameError("No track exists that accepts '%s'" % segment_type)
        if count > 1: raise NameError("Multiple tracks exist that accept '%s', please specify track name" % segment_type)

        return next(track for track in self.tracks.values() if track.accept_segment_type == segment_type)

    def add_segment(self, segment: Union[VideoSegment, StickerSegment, AudioSegment, TextSegment, EffectSegment, FilterSegment],
                    track_name: Optional[str] = None) -> "ScriptFile":
        """Add a segment to the specified track

        Args:
            segment (`VideoSegment`, `StickerSegment`, `AudioSegment`, `TextSegment`, or `EffectSegment`): Segment to add
            track_name (`str`, optional): Target track name. Omissible if only one track of this type exists.

        Raises:
            `NameError`: Specified track name not found, or `track_name` missing when required.
            `TypeError`: Segment type does not match track type.
            `SegmentOverlap`: New segment overlaps with existing segments.
        """
        target = self._get_track(type(segment), track_name)

        # Add to track and update duration
        target.add_segment(segment)
        self.duration = max(self.duration, segment.end)

        # Auto-add related materials
        if isinstance(segment, VideoSegment):
            # Animations
            if (segment.animations_instance is not None) and (segment.animations_instance not in self.materials):
                self.materials.animations.append(segment.animations_instance)
            # Effects
            for effect in segment.effects:
                if effect not in self.materials:
                    self.materials.video_effects.append(effect)
            # Filters
            for filter_ in segment.filters:
                if filter_ not in self.materials:
                    self.materials.filters.append(filter_)
            # Mix modes
            for mix_mode in segment.mix_modes:
                if mix_mode not in self.materials:
                    self.materials.mix_modes.append(mix_mode)
            # Masks
            if segment.mask is not None:
                self.materials.masks.append(segment.mask.export_json())
            # Transitions
            if (segment.transition is not None) and (segment.transition not in self.materials):
                self.materials.transitions.append(segment.transition)
            # Background filling
            if segment.background_filling is not None:
                self.materials.canvases.append(segment.background_filling)
            # Audio fade-in/out
            if (segment.fade is not None) and (segment.fade not in self.materials):
                self.materials.audio_fades.append(segment.fade)

            self.materials.speeds.append(segment.speed)
        elif isinstance(segment, StickerSegment):
            self.materials.stickers.append(segment.export_material())
        elif isinstance(segment, AudioSegment):
            # Fade in/out
            if (segment.fade is not None) and (segment.fade not in self.materials):
                self.materials.audio_fades.append(segment.fade)
            # Effects
            for effect in segment.effects:
                if effect not in self.materials:
                    self.materials.audio_effects.append(effect)
            self.materials.speeds.append(segment.speed)
        elif isinstance(segment, TextSegment):
            # Animations
            if (segment.animations_instance is not None) and (segment.animations_instance not in self.materials):
                self.materials.animations.append(segment.animations_instance)
            # Bubble effects
            if segment.bubble is not None:
                self.materials.filters.append(segment.bubble)
            # Text effects
            if segment.effect is not None:
                self.materials.filters.append(segment.effect)
            # Font styles
            self.materials.texts.append(segment.export_material())
        elif isinstance(segment, EffectSegment):
            # Effect materials
            if segment.effect_inst not in self.materials:
                self.materials.video_effects.append(segment.effect_inst)
        elif isinstance(segment, FilterSegment):
            # Filter materials
            if segment.material not in self.materials:
                self.materials.filters.append(segment.material)

        # Add segment materials
        if isinstance(segment, (VideoSegment, AudioSegment)):
            self.add_material(segment.material_instance)

        return self

    def add_effect(self, effect: Union[VideoSceneEffectType, VideoCharacterEffectType],
                   t_range: Timerange, track_name: Optional[str] = None, *,
                   params: Optional[List[Optional[float]]] = None) -> "ScriptFile":
        """Add an effect segment to the specified effect track

        Args:
            effect (`VideoSceneEffectType` or `VideoCharacterEffectType`): Effect type
            t_range (`Timerange`): Time range of the effect segment
            track_name (`str`, optional): Target track name. Omissible if only one effect track exists.
            params (`List[Optional[float]]`, optional): List of effect parameters, 
                items provided as None use default values. Range (0~100).
                Refer to annotations in the enum members for parameter order.

        Raises:
            `NameError`: Specified track name not found, or `track_name` missing when required.
            `TypeError`: Specified track is not an effect track.
            `ValueError`: Overlaps with existing segments, parameter count exceeds limit, or parameter out of range.
        """
        target = self._get_track(EffectSegment, track_name)

        # Add to track and update duration
        segment = EffectSegment(effect, t_range, params)
        target.add_segment(segment)
        self.duration = max(self.duration, t_range.start + t_range.duration)

        # Auto-add related materials
        if segment.effect_inst not in self.materials:
            self.materials.video_effects.append(segment.effect_inst)
        return self

    def add_filter(self, filter_meta: FilterType, t_range: Timerange,
                   track_name: Optional[str] = None, intensity: float = 100.0) -> "ScriptFile":
        """Add a filter segment to the specified filter track

        Args:
            filter_meta (`FilterType`): Filter type
            t_range (`Timerange`): Time range of the filter segment
            track_name (`str`, optional): Target track name. Omissible if only one filter track exists.
            intensity (`float`, optional): Filter intensity (0-100). Valid only if filter supports it. Default is 100.

        Raises:
            `NameError`: Specified track name not found, or `track_name` missing when required.
            `TypeError`: Specified track is not a filter track.
            `ValueError`: New segment overlaps with existing segments.
        """
        target = self._get_track(FilterSegment, track_name)

        # Add to track and update duration
        segment = FilterSegment(filter_meta, t_range, intensity / 100.0)  # Convert to 0-1 range
        target.add_segment(segment)
        self.duration = max(self.duration, t_range.end)

        # Auto-add related materials
        self.materials.filters.append(segment.material)
        return self

    def import_srt(self, srt_path: str, track_name: str, *,
                   time_offset: Union[str, float] = 0.0,
                   style_reference: Optional[TextSegment] = None,
                   text_style: TextStyle = TextStyle(size=5, align=1, auto_wrapping=True),
                   clip_settings: Optional[ClipSettings] = ClipSettings(transform_y=-0.8)) -> "ScriptFile":
        """Import subtitles from an SRT file, supports using a `TextSegment` as style reference.

        Note: By default, the `clip_settings` of the reference segment is NOT used. 
        Pass `clip_settings=None` if you want to use it.

        Args:
            srt_path (`str`): SRT file path
            track_name (`str`): Target text track name, created automatically if it doesn't exist.
            style_reference (`TextSegment`, optional): Text segment used as style reference.
            time_offset (`Union[str, float]`, optional): Global subtitle time offset in microseconds. Default is 0.
            text_style (`TextStyle`, optional): Subtitle style, defaults to CapCut's style. Overridden by `style_reference`.
            clip_settings (`ClipSettings`, optional): Image adjustment settings, defaults to CapCut's settings. 
                                                     Overrides `style_reference` settings unless specified as `None`.

        Raises:
            `NameError`: Track with same name exists.
            `TypeError`: Track type mismatch.
        """
        if style_reference is None and clip_settings is None:
            raise ValueError("Please provide `clip_settings` if no style reference is provided")

        time_offset = tim(time_offset)
        if track_name not in self.tracks:
            self.add_track(TrackType.text, track_name, relative_index=999)  # Topmost layer for all text tracks

        with open(srt_path, "r", encoding="utf-8-sig") as srt_file:
            lines = srt_file.readlines()

        def __add_text_segment(text: str, t_range: Timerange) -> None:
            if style_reference:
                seg = TextSegment.create_from_template(text, t_range, style_reference)
                if clip_settings is not None:
                    seg.clip_settings = deepcopy(clip_settings)
            else:
                seg = TextSegment(text, t_range, style=text_style, clip_settings=clip_settings)
            self.add_segment(seg, track_name)

        index = 0
        text: str = ""
        text_trange: Timerange
        read_state: Literal["index", "timestamp", "content"] = "index"
        while index < len(lines):
            line = lines[index].strip()
            if read_state == "index":
                if len(line) == 0:
                    index += 1
                    continue
                if not line.isdigit():
                    raise ValueError("Expected a number at line %d, got '%s'" % (index+1, line))
                index += 1
                read_state = "timestamp"
            elif read_state == "timestamp":
                # Read timestamp
                start_str, end_str = line.split(" --> ")
                start, end = srt_tstamp(start_str), srt_tstamp(end_str)
                text_trange = Timerange(start + time_offset, end - start)

                index += 1
                read_state = "content"
            elif read_state == "content":
                # Content ended, generate segment
                if len(line) == 0:
                    __add_text_segment(text.strip(), text_trange)

                    text = ""
                    read_state = "index"
                else:
                    text += line + "\n"
                index += 1

        # Add the last segment
        if len(text) > 0:
            __add_text_segment(text.strip(), text_trange)

        return self

    def get_imported_track(self, track_type: Literal[TrackType.video, TrackType.audio, TrackType.text],
                           name: Optional[str] = None, index: Optional[int] = None) -> EditableTrack:
        """Get an imported track of specified type for replacement.

        Recommended to filter by track name if known.

        Args:
            track_type (`TrackType.video`, `TrackType.audio` or `TrackType.text`): Track type (Audio/Video/Text)
            name (`str`, optional): Track name.
            index (`int`, optional): Index among imported tracks of same type (0 for bottom layer).

        Raises:
            `TrackNotFound`: No matching track found.
            `AmbiguousTrack`: Multiple matching tracks found.
        """
        tracks_of_same_type: List[EditableTrack] = []
        for track in self.imported_tracks:
            if track.track_type == track_type:
                assert isinstance(track, EditableTrack)
                tracks_of_same_type.append(track)

        ret: List[EditableTrack] = []
        for ind, track in enumerate(tracks_of_same_type):
            if (name is not None) and (track.name != name): continue
            if (index is not None) and (ind != index): continue
            ret.append(track)

        if len(ret) == 0:
            raise exceptions.TrackNotFound(
                "No matching track found: track_type=%s, name=%s, index=%s" % (track_type, name, index))
        if len(ret) > 1:
            raise exceptions.AmbiguousTrack(
                "Multiple matching tracks found: track_type=%s, name=%s, index=%s" % (track_type, name, index))

        return ret[0]

    def import_track(self, source_file: "ScriptFile", track: EditableTrack, *,
                     offset: Union[str, int] = 0,
                     new_name: Optional[str] = None, relative_index: Optional[int] = None) -> "ScriptFile":
        """Import an `EditableTrack` into the current `ScriptFile`, e.g., from a template.

        Note: This method preserves material IDs, so importing the same track multiple times is not supported.

        Args:
            source_file (`ScriptFile`): Source file containing the track
            track (`EditableTrack`): Track to import, obtain via `get_imported_track`.
            offset (`str | int`, optional): Time offset in microseconds or time string (e.g., "1s").
            new_name (`str`, optional): New track name, defaults to source track name.
            relative_index (`int`, optional): Relative index to adjust rendering layer.
        """
        # Copy original track structure, adjust render layer as needed
        imported_track = deepcopy(track)
        if relative_index is not None:
            imported_track.render_index = track.track_type.value.render_index + relative_index
        if new_name is not None:
            imported_track.name = new_name

        # Apply offset
        offset_us = tim(offset)
        if offset_us != 0:
            for seg in imported_track.segments:
                seg.target_timerange.start = max(0, seg.target_timerange.start + offset_us)
        self.imported_tracks.append(imported_track)

        # Collect all material IDs to copy
        material_ids = set()
        segments: List[Dict[str, Any]] = track.raw_data.get("segments", [])
        for segment in segments:
            # Main material ID
            material_id = segment.get("material_id")
            if material_id:
                material_ids.add(material_id)

            # Material IDs in extra_material_refs
            extra_refs: List[str] = segment.get("extra_material_refs", [])
            material_ids.update(extra_refs)

        # Copy materials
        for material_type, material_list in source_file.imported_materials.items():
            for material in material_list:
                if material.get("id") in material_ids:
                    if material_type not in self.imported_materials:
                        self.imported_materials[material_type] = []
                    self.imported_materials[material_type].append(deepcopy(material))
                    material_ids.remove(material.get("id"))

        assert len(material_ids) == 0, "Following materials not found: %s" % material_ids

        # Update total duration
        self.duration = max(self.duration, track.end_time)

        return self

    def replace_material_by_name(self, material_name: str, material: Union[VideoMaterial, AudioMaterial],
                                 replace_crop: bool = False) -> "ScriptFile":
        """Replace material with specified name, affects all segments referencing it.

        This method does not change segment duration or source reference range (`source_timerange`),
        especially suitable for image materials.

        Args:
            material_name (`str`): Name of material to replace
            material (`VideoMaterial` or `AudioMaterial`): New material, currently only video and audio supported
            replace_crop (`bool`, optional): Whether to replace original crop settings. Only valid for video materials.

        Raises:
            `MaterialNotFound`: No material of the same type found with specified name
            `AmbiguousMaterial`: Multiple materials of the same type found with specified name
        """
        video_mode = isinstance(material, VideoMaterial)
        # Find material
        target_json_obj: Optional[Dict[str, Any]] = None
        target_material_list = self.imported_materials["videos" if video_mode else "audios"]
        name_key = "material_name" if video_mode else "name"
        for mat in target_material_list:
            if mat[name_key] == material_name:
                if target_json_obj is not None:
                    raise exceptions.AmbiguousMaterial(
                        "Found multiple materials named '%s' with type '%s'" % (material_name, type(material)))
                target_json_obj = mat
        if target_json_obj is None:
            raise exceptions.MaterialNotFound("Material named '%s' with type '%s' not found" % (material_name, type(material)))

        # Update material info
        target_json_obj.update({name_key: material.material_name, "path": material.path, "duration": material.duration})
        if video_mode:
            target_json_obj.update({"width": material.width, "height": material.height, "material_type": material.material_type})
            if replace_crop:
                target_json_obj.update({"crop": material.crop_settings.export_json()})

        return self

    def replace_material_by_seg(self, track: EditableTrack, segment_index: int, material: Union[VideoMaterial, AudioMaterial],
                                source_timerange: Optional[Timerange] = None, *,
                                handle_shrink: ShrinkMode = ShrinkMode.cut_tail,
                                handle_extend: Union[ExtendMode, List[ExtendMode]] = ExtendMode.cut_material_tail) -> "ScriptFile":
        """Replace material for specified segment on audio/video track. Material replacement for speed-changed segments not yet supported.

        Args:
            track (`EditableTrack`): Track containing segment, obtained via `get_imported_track`
            segment_index (`int`): Index of segment to replace, starting from 0
            material (`VideoMaterial` or `AudioMaterial`): New material, must match original material type
            source_timerange (`Timerange`, optional): Clip range from new material. Defaults to full duration, or segment duration for images.
            handle_shrink (`ShrinkMode`, optional): Handling method when new material is shorter. Defaults to cutting tail to match material length.
            handle_extend (`ExtendMode` or `List[ExtendMode]`, optional): Handling method when new material is longer. Will try sequentially.
                Defaults to truncating material tail to maintain original segment length.

        Raises:
            `IndexError`: `segment_index` out of bounds
            `TypeError`: Incorrect track or material type
            `ExtensionFailed`: Failed to handle material extension
        """
        if not isinstance(track, ImportedMediaTrack):
            raise TypeError("Specified track (type %s) does not support material replacement" % track.track_type)
        if not 0 <= segment_index < len(track):
            raise IndexError("Segment index %d out of range [0, %d)" % (segment_index, len(track)))
        if not track.check_material_type(material):
            raise TypeError("Specified material type %s does not match track type %s", (type(material), track.track_type))
        seg = track.segments[segment_index]

        if isinstance(handle_extend, ExtendMode):
            handle_extend = [handle_extend]
        if source_timerange is None:
            if isinstance(material, VideoMaterial) and (material.material_type == "photo"):
                source_timerange = Timerange(0, seg.duration)
            else:
                source_timerange = Timerange(0, material.duration)

        # Handle time changes
        track.process_timerange(segment_index, source_timerange, handle_shrink, handle_extend)

        # Finally replace material links
        track.segments[segment_index].material_id = material.material_id
        self.add_material(material)

        # TODO: Update total duration
        return self

    def replace_text(self, track: EditableTrack, segment_index: int, text: Union[str, List[str]],
                     recalc_style: bool = True) -> "ScriptFile":
        """Replace text content for specified segment on text track. Supports normal text or text templates.

        Args:
            track (`EditableTrack`): Text track containing segment, obtained via `get_imported_track`
            segment_index (`int`): Index of segment to replace, starting from 0
            text (`str` or `List[str]`): New text content. For templates, pass a list of strings.
            recalc_style (`bool`): Whether to recalculate font style distribution to maintain original ratios. Default is True.

        Raises:
            `IndexError`: `segment_index` out of bounds
            `TypeError`: Incorrect track type
            `ValueError`: Mismatched text count for template
        """
        if not isinstance(track, ImportedTextTrack):
            raise TypeError("Specified track (type %s) does not support text replacement" % track.track_type)
        if not 0 <= segment_index < len(track):
            raise IndexError("Segment index %d out of range [0, %d)" % (segment_index, len(track)))

        def __recalc_style_range(old_len: int, new_len: int, styles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
            """Adjust font style distribution"""
            new_styles: List[Dict[str, Any]] = []
            for style in styles:
                start = math.ceil(style["range"][0] / old_len * new_len)
                end = math.ceil(style["range"][1] / old_len * new_len)
                style["range"] = [start, end]
                if start != end:
                    new_styles.append(style)
            return new_styles

        replaced: bool = False
        material_id: str = track.segments[segment_index].material_id
        # Try replacing in text materials
        for mat in self.imported_materials["texts"]:
            if mat["id"] != material_id:
                continue

            if isinstance(text, list):
                if len(text) != 1:
                    raise ValueError(f"Normal text segment can only have one text content, but provided {text}")
                text = text[0]

            content = json.loads(mat["content"])
            if recalc_style:
                content["styles"] = __recalc_style_range(len(content["text"]), len(text), content["styles"])
            content["text"] = text
            mat["content"] = json.dumps(content, ensure_ascii=False)
            replaced = True
            break
        if replaced:
            return self

        # Try replacing in text templates
        for template in self.imported_materials["text_templates"]:
            if template["id"] != material_id:
                continue

            resources = template["text_info_resources"]
            if isinstance(text, str):
                text = [text]
            if len(text) > len(resources):
                raise ValueError(f"Text template '{template['name']}' has only {len(resources)} text segments, but provided {len(text)}")

            for sub_material_id, new_text in zip(map(lambda x: x["text_material_id"], resources), text):
                for mat in self.imported_materials["texts"]:
                    if mat["id"] != sub_material_id:
                        continue

                    try:
                        content = json.loads(mat["content"])
                        if recalc_style:
                            content["styles"] = __recalc_style_range(len(content["text"]), len(new_text), content["styles"])
                        content["text"] = new_text
                        mat["content"] = json.dumps(content, ensure_ascii=False)
                    except json.JSONDecodeError:
                        mat["content"] = new_text
                    except TypeError:
                        mat["content"] = new_text

                    break
            replaced = True
            break

        assert replaced, f"Material {material_id} for specified segment not found"

        return self

    def inspect_material(self) -> None:
        """Inspect metadata for imported stickers, text bubbles, and font effects in draft"""
        print("Sticker materials:")
        for sticker in self.imported_materials["stickers"]:
            print("\tResource id: %s '%s'" % (sticker["resource_id"], sticker.get("name", "")))

        print("Text bubble effects:")
        for effect in self.imported_materials["effects"]:
            if effect["type"] == "text_shape":
                print("\tEffect id: %s ,Resource id: %s '%s'" %
                      (effect["effect_id"], effect["resource_id"], effect.get("name", "")))

        print("Font effects:")
        for effect in self.imported_materials["effects"]:
            if effect["type"] == "text_effect":
                print("\tResource id: %s '%s'" % (effect["resource_id"], effect.get("name", "")))

    def dumps(self) -> str:
        """Export draft content as JSON string"""
        self.content["fps"] = self.fps
        self.content["duration"] = self.duration
        self.content["config"]["maintrack_adsorb"] = self.maintrack_adsorb
        self.content["canvas_config"] = {"width": self.width, "height": self.height, "ratio": "original"}
        self.content["materials"] = self.materials.export_json()

        # Merge imported materials
        for material_type, material_list in self.imported_materials.items():
            if material_type not in self.content["materials"]:
                self.content["materials"][material_type] = material_list
            else:
                self.content["materials"][material_type].extend(material_list)

        # Sort tracks and export
        track_list: List[BaseTrack] = list(self.imported_tracks + list(self.tracks.values()))  # New tracks added at the end (top layer)
        track_list.sort(key=lambda track: track.render_index)
        self.content["tracks"] = [track.export_json() for track in track_list]

        return json.dumps(self.content, ensure_ascii=False, indent=4)

    def dump(self, file_path: str) -> None:
        """Write draft content to file"""
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(self.dumps())

    def save(self) -> None:
        """Save draft file to original path

        Raises:
            `ValueError`: Save path not set
        """
        if self.save_path is None:
            raise ValueError("Save path not set, possibly not in template mode")
        
        # Save to main file
        self.dump(self.save_path)
        
        # If dual file compatibility mode enabled, save to the other file as well
        if self.dual_file_compatibility:
            draft_dir = os.path.dirname(self.save_path)
            if "draft_content.json" in self.save_path and "draft_info.json" not in self.save_path:
                # Currently saving draft_content.json, also save to draft_info.json
                alt_path = os.path.join(draft_dir, "draft_info.json")
                self.dump(alt_path)
            elif "draft_info.json" in self.save_path and "draft_content.json" not in self.save_path:
                # Currently saving draft_info.json, also save to draft_content.json
                alt_path = os.path.join(draft_dir, "draft_content.json")
                self.dump(alt_path)
