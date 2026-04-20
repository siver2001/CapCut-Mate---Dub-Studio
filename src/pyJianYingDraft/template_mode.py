"""Classes and functions related to template mode"""

from enum import Enum
from copy import deepcopy

from . import util
from . import exceptions
from .time_util import Timerange
from .segment import BaseSegment
from .track import BaseTrack, TrackType
from .local_materials import VideoMaterial, AudioMaterial

from typing import List, Dict, Any

class ShrinkMode(Enum):
    """Methods for handling cases where replacement material is shorter than the original"""

    cut_head = "cut_head"
    """Cut head, i.e., move segment start point forward"""
    cut_tail = "cut_tail"
    """Cut tail, i.e., move segment end point backward"""

    cut_tail_align = "cut_tail_align"
    """Cut tail and close gap, i.e., move segment end point backward and shift subsequent segments backward accordingly"""

    shrink = "shrink"
    """Keep midpoint fixed, move both endpoints towards the center"""

class ExtendMode(Enum):
    """Methods for handling cases where replacement material is longer than the original"""

    cut_material_tail = "cut_material_tail"
    """Cut material tail (overrides `source_timerange` parameter) to keep segment duration unchanged. This method always succeeds."""

    extend_head = "extend_head"
    """Extend head, i.e., try to move segment start point backward. Fails if it overlaps with the previous segment."""
    extend_tail = "extend_tail"
    """Extend tail, i.e., try to move segment end point forward. Fails if it overlaps with the next segment."""

    push_tail = "push_tail"
    """Extend tail, shifting subsequent segments forward if necessary. This method always succeeds."""

class ImportedSegment(BaseSegment):
    """Imported segment"""

    raw_data: Dict[str, Any]
    """Original JSON data"""

    __DATA_ATTRS = ["material_id", "target_timerange"]
    def __init__(self, json_data: Dict[str, Any]):
        self.raw_data = deepcopy(json_data)

        util.assign_attr_with_json(self, self.__DATA_ATTRS, json_data)

    def export_json(self) -> Dict[str, Any]:
        json_data = deepcopy(self.raw_data)
        json_data.update(util.export_attr_to_json(self, self.__DATA_ATTRS))
        return json_data

class ImportedMediaSegment(ImportedSegment):
    """Imported video/audio segment"""

    source_timerange: Timerange
    """Time range of the material used by the segment"""

    __DATA_ATTRS = ["source_timerange"]
    def __init__(self, json_data: Dict[str, Any]):
        super().__init__(json_data)

        util.assign_attr_with_json(self, self.__DATA_ATTRS, json_data)

    def export_json(self) -> Dict[str, Any]:
        json_data = super().export_json()
        json_data.update(util.export_attr_to_json(self, self.__DATA_ATTRS))
        return json_data


class ImportedTrack(BaseTrack):
    """Track imported in template mode"""

    raw_data: Dict[str, Any]
    """Original track data"""

    def __init__(self, json_data: Dict[str, Any]):
        self.track_type = TrackType.from_name(json_data["type"])
        self.name = json_data["name"]
        self.track_id = json_data["id"]
        self.render_index = max([int(seg["render_index"]) for seg in json_data["segments"]], default=0)

        self.raw_data = deepcopy(json_data)

    def export_json(self) -> Dict[str, Any]:
        ret = deepcopy(self.raw_data)
        ret.update({
            "name": self.name,
            "id": self.track_id
        })
        return ret

class EditableTrack(ImportedTrack):
    """Importable and editable tracks in template mode (audio/video and text tracks)"""

    segments: List[ImportedSegment]
    """List of segments contained in this track"""

    def __len__(self):
        return len(self.segments)

    @property
    def start_time(self) -> int:
        """Track start time, microseconds"""
        if len(self.segments) == 0:
            return 0
        return self.segments[0].target_timerange.start

    @property
    def end_time(self) -> int:
        """Track end time, microseconds"""
        if len(self.segments) == 0:
            return 0
        return self.segments[-1].target_timerange.end

    def export_json(self) -> Dict[str, Any]:
        ret = super().export_json()
        # Write render_index for each segment
        segment_exports = [seg.export_json() for seg in self.segments]
        for seg in segment_exports:
            seg["render_index"] = self.render_index
        ret["segments"] = segment_exports
        return ret

class ImportedTextTrack(EditableTrack):
    """Text track imported in template mode"""

    def __init__(self, json_data: Dict[str, Any]):
        super().__init__(json_data)
        self.segments = [ImportedSegment(seg) for seg in json_data["segments"]]

class ImportedMediaTrack(EditableTrack):
    """Audio/video track imported in template mode"""

    segments: List[ImportedMediaSegment]
    """List of segments contained in this track"""

    def __init__(self, json_data: Dict[str, Any]):
        super().__init__(json_data)
        self.segments = [ImportedMediaSegment(seg) for seg in json_data["segments"]]

    def check_material_type(self, material: object) -> bool:
        """Check if material type matches the track type"""
        if self.track_type == TrackType.video and isinstance(material, VideoMaterial):
            return True
        if self.track_type == TrackType.audio and isinstance(material, AudioMaterial):
            return True
        return False

    def process_timerange(self, seg_index: int, src_timerange: Timerange,
                          shrink: ShrinkMode, extend: List[ExtendMode]) -> None:
        """Handle time range changes during material replacement"""
        seg = self.segments[seg_index]
        new_duration = src_timerange.duration

        # Duration decreased
        delta_duration = abs(new_duration - seg.duration)
        if new_duration < seg.duration:
            if shrink == ShrinkMode.cut_head:
                seg.start += delta_duration
            elif shrink == ShrinkMode.cut_tail:
                seg.duration -= delta_duration
            elif shrink == ShrinkMode.cut_tail_align:
                seg.duration -= delta_duration
                for i in range(seg_index+1, len(self.segments)):  # Subsequent segments also shift backward accordingly (maintaining gaps)
                    self.segments[i].start -= delta_duration
            elif shrink == ShrinkMode.shrink:
                seg.duration -= delta_duration
                seg.start += delta_duration // 2
            else:
                raise ValueError(f"Unsupported shrink mode: {shrink}")
        # Duration increased
        elif new_duration > seg.duration:
            success_flag = False
            prev_seg_end = int(0) if seg_index == 0 else self.segments[seg_index-1].target_timerange.end
            next_seg_start = int(1e15) if seg_index == len(self.segments)-1 else self.segments[seg_index+1].start
            for mode in extend:
                if mode == ExtendMode.extend_head:
                    if seg.start - delta_duration >= prev_seg_end:
                        seg.start -= delta_duration
                        success_flag = True
                elif mode == ExtendMode.extend_tail:
                    if seg.target_timerange.end + delta_duration <= next_seg_start:
                        seg.duration += delta_duration
                        success_flag = True
                elif mode == ExtendMode.push_tail:
                    shift_duration = max(0, seg.target_timerange.end + delta_duration - next_seg_start)
                    seg.duration += delta_duration
                    if shift_duration > 0:  # Shift subsequent segments forward if necessary
                        for i in range(seg_index+1, len(self.segments)):
                            self.segments[i].start += shift_duration
                    success_flag = True
                elif mode == ExtendMode.cut_material_tail:
                    src_timerange.duration = seg.duration
                    success_flag = True
                else:
                    raise ValueError(f"Unsupported extend mode: {mode}")

                if success_flag:
                    break
            if not success_flag:
                raise exceptions.ExtensionFailed(f"Failed to extend segment to {new_duration}μs using methods: {extend}")

        # Write material time range
        seg.source_timerange = src_timerange

def import_track(json_data: Dict[str, Any]) -> ImportedTrack:
    """Import track"""
    track_type = TrackType.from_name(json_data["type"])
    if not track_type.value.allow_modify:
        return ImportedTrack(json_data)
    if track_type == TrackType.text:
        return ImportedTextTrack(json_data)
    return ImportedMediaTrack(json_data)
