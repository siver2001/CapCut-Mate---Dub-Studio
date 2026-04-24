import json
import os
import subprocess
import uuid

from typing import Optional, Literal
from typing import Dict, Any

try:
    import pymediainfo  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    pymediainfo = None  # type: ignore


_STILL_IMAGE_EXTENSIONS = {
    ".bmp",
    ".heic",
    ".jpeg",
    ".jpg",
    ".png",
    ".tif",
    ".tiff",
    ".webp",
}


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _duration_us_from_seconds(value: Any) -> int:
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        seconds = 0.0
    return max(int(seconds * 1_000_000), 0)


def _ffprobe_json(path: str) -> Dict[str, Any]:
    completed = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            path,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout or "{}")


def _first_stream(probe: Dict[str, Any], codec_type: str) -> Optional[Dict[str, Any]]:
    for stream in probe.get("streams", []):
        if stream.get("codec_type") == codec_type:
            return stream
    return None


def _probe_visual_metadata(path: str, postfix: str) -> Dict[str, Any]:
    probe = _ffprobe_json(path)
    video_stream = _first_stream(probe, "video") or {}
    width = _safe_int(video_stream.get("width"), 0)
    height = _safe_int(video_stream.get("height"), 0)
    duration_us = _duration_us_from_seconds(
        video_stream.get("duration") or probe.get("format", {}).get("duration")
    )

    if postfix.lower() in _STILL_IMAGE_EXTENSIONS:
        if width <= 0 or height <= 0:
            raise ValueError(f"Could not detect image dimensions for {path}")
        return {
            "material_type": "photo",
            "duration": 10_800_000_000,
            "width": width,
            "height": height,
        }

    if width <= 0 or height <= 0:
        raise ValueError(f"Input material {path} has no video or image tracks")

    return {
        "material_type": "video",
        "duration": max(duration_us, 1),
        "width": width,
        "height": height,
    }


def _probe_audio_duration_us(path: str) -> int:
    probe = _ffprobe_json(path)
    if _first_stream(probe, "video"):
        raise ValueError("Audio materials should not contain video tracks")
    audio_stream = _first_stream(probe, "audio") or {}
    if not audio_stream:
        raise ValueError(f"Given material file {path} has no audio tracks")
    duration_us = _duration_us_from_seconds(
        audio_stream.get("duration") or probe.get("format", {}).get("duration")
    )
    if duration_us <= 0:
        raise ValueError(f"Could not determine audio duration for {path}")
    return duration_us

class CropSettings:
    """Crop settings for materials, each attribute is between 0-1. Note the origin is at the top-left corner."""

    upper_left_x: float
    upper_left_y: float
    upper_right_x: float
    upper_right_y: float
    lower_left_x: float
    lower_left_y: float
    lower_right_x: float
    lower_right_y: float

    def __init__(self, *, upper_left_x: float = 0.0, upper_left_y: float = 0.0,
                 upper_right_x: float = 1.0, upper_right_y: float = 0.0,
                 lower_left_x: float = 0.0, lower_left_y: float = 1.0,
                 lower_right_x: float = 1.0, lower_right_y: float = 1.0):
        """Initialize crop settings, defaults mean no cropping"""
        self.upper_left_x = upper_left_x
        self.upper_left_y = upper_left_y
        self.upper_right_x = upper_right_x
        self.upper_right_y = upper_right_y
        self.lower_left_x = lower_left_x
        self.lower_left_y = lower_left_y
        self.lower_right_x = lower_right_x
        self.lower_right_y = lower_right_y

    def export_json(self) -> Dict[str, Any]:
        return {
            "upper_left_x": self.upper_left_x,
            "upper_left_y": self.upper_left_y,
            "upper_right_x": self.upper_right_x,
            "upper_right_y": self.upper_right_y,
            "lower_left_x": self.lower_left_x,
            "lower_left_y": self.lower_left_y,
            "lower_right_x": self.lower_right_x,
            "lower_right_y": self.lower_right_y
        }

class VideoMaterial:
    """Local video material (video or image). A single material can be used in multiple segments."""

    material_id: str
    """Global material ID, auto-generated"""
    local_material_id: str
    """Local material ID, purpose not yet clear"""
    material_name: str
    """Material name"""
    path: str
    """Material file path"""
    duration: int
    """Material duration in microseconds"""
    height: int
    """Material height"""
    width: int
    """Material width"""
    crop_settings: CropSettings
    """Material crop settings"""
    material_type: Literal["video", "photo"]
    """Material type: video or photo"""

    def __init__(self, path: str, material_name: Optional[str] = None, crop_settings: CropSettings = CropSettings()):
        """Load video (or image) material from specified location

        Args:
            path (`str`): Material file path. Supports common video (mp4, mov, avi) and image (jpg, jpeg, png) files.
            material_name (`str`, optional): Material name. Defaults to filename if not specified.
            crop_settings (`CropSettings`, optional): Material crop settings. Defaults to no cropping.

        Raises:
            `FileNotFoundError`: Material file does not exist.
            `ValueError`: Unsupported material file type.
        """
        path = os.path.abspath(path)
        postfix = os.path.splitext(path)[1]
        if not os.path.exists(path):
            raise FileNotFoundError(f"Could not find {path}")

        self.material_name = material_name if material_name else os.path.basename(path)
        self.material_id = uuid.uuid4().hex
        self.path = path
        self.crop_settings = crop_settings
        self.local_material_id = ""

        metadata: Dict[str, Any] | None = None
        if pymediainfo is not None:
            try:
                if pymediainfo.MediaInfo.can_parse():
                    info = pymediainfo.MediaInfo.parse(
                        path,
                        mediainfo_options={"File_TestContinuousFileNames": "0"},
                    )
                    if len(info.video_tracks):
                        metadata = {
                            "material_type": "video",
                            "duration": max(int(info.video_tracks[0].duration * 1e3), 1),  # type: ignore
                            "width": int(info.video_tracks[0].width),  # type: ignore
                            "height": int(info.video_tracks[0].height),  # type: ignore
                        }
                    elif len(info.image_tracks):
                        metadata = {
                            "material_type": "photo",
                            "duration": 10800000000,
                            "width": int(info.image_tracks[0].width),  # type: ignore
                            "height": int(info.image_tracks[0].height),  # type: ignore
                        }
            except Exception:
                metadata = None

        if metadata is None:
            metadata = _probe_visual_metadata(path, postfix)

        self.material_type = metadata["material_type"]
        self.duration = int(metadata["duration"])
        self.width = int(metadata["width"])
        self.height = int(metadata["height"])

    def export_json(self) -> Dict[str, Any]:
        video_material_json = {
            "audio_fade": None,
            "category_id": "",
            "category_name": "local",
            "check_flag": 63487,
            "crop": self.crop_settings.export_json(),
            "crop_ratio": "free",
            "crop_scale": 1.0,
            "duration": self.duration,
            "height": self.height,
            "id": self.material_id,
            "local_material_id": self.local_material_id,
            "material_id": self.material_id,
            "material_name": self.material_name,
            "media_path": "",
            "path": self.path,
            "type": self.material_type,
            "width": self.width
        }
        return video_material_json

class AudioMaterial:
    """Local audio material"""

    material_id: str
    """Global material ID, auto-generated"""
    material_name: str
    """Material name"""
    path: str
    """Material file path"""

    duration: int
    """Material duration in microseconds"""

    def __init__(self, path: str, material_name: Optional[str] = None):
        """Load audio material from specified location. Note: Video files should not be used as audio materials.

        Args:
            path (`str`): Material file path. Supports common audio files (mp3, wav).
            material_name (`str`, optional): Material name. Defaults to filename if not specified.

        Raises:
            `FileNotFoundError`: Material file does not exist.
            `ValueError`: Unsupported material file type.
        """
        path = os.path.abspath(path)
        if not os.path.exists(path):
            raise FileNotFoundError(f"Could not find {path}")

        self.material_name = material_name if material_name else os.path.basename(path)
        self.material_id = uuid.uuid4().hex
        self.path = path

        duration_us: int | None = None
        if pymediainfo is not None:
            try:
                if pymediainfo.MediaInfo.can_parse():
                    info = pymediainfo.MediaInfo.parse(path)  # type: ignore
                    if len(info.video_tracks):
                        raise ValueError("Audio materials should not contain video tracks")
                    if not len(info.audio_tracks):
                        raise ValueError(f"Given material file {path} has no audio tracks")
                    duration_us = max(int(info.audio_tracks[0].duration * 1e3), 1)  # type: ignore
            except ValueError:
                raise
            except Exception:
                duration_us = None

        if duration_us is None:
            duration_us = _probe_audio_duration_us(path)

        self.duration = duration_us

    def export_json(self) -> Dict[str, Any]:
        return {
            "app_id": 0,
            "category_id": "",
            "category_name": "local",
            "check_flag": 3,
            "copyright_limit_type": "none",
            "duration": self.duration,
            "effect_id": "",
            "formula_id": "",
            "id": self.material_id,
            "local_material_id": self.material_id,
            "music_id": self.material_id,
            "name": self.material_name,
            "path": self.path,
            "source_platform": 0,
            "type": "extract_music",
            "wave_points": []
        }
