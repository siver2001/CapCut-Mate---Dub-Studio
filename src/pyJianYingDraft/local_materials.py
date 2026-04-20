import os
import uuid
import pymediainfo

from typing import Optional, Literal
from typing import Dict, Any

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

        if not pymediainfo.MediaInfo.can_parse():
            raise ValueError(f"Unsupported video material type '{postfix}'")

        info: pymediainfo.MediaInfo = \
            pymediainfo.MediaInfo.parse(path, mediainfo_options={"File_TestContinuousFileNames": "0"})  # type: ignore
        # Treated as video material if it has video tracks
        if len(info.video_tracks):
            self.material_type = "video"
            self.duration = int(info.video_tracks[0].duration * 1e3)  # type: ignore
            self.width, self.height = info.video_tracks[0].width, info.video_tracks[0].height  # type: ignore
        # For gif files, use imageio to get duration
        elif postfix.lower() == ".gif":
            import imageio
            gif = imageio.get_reader(path)

            self.material_type = "video"
            self.duration = int(round(gif.get_meta_data()['duration'] * gif.get_length() * 1e3))
            self.width, self.height = info.image_tracks[0].width, info.image_tracks[0].height  # type: ignore
            gif.close()
        elif len(info.image_tracks):
            self.material_type = "photo"
            self.duration = 10800000000  # Equivalent to 3 hours
            self.width, self.height = info.image_tracks[0].width, info.image_tracks[0].height  # type: ignore
        else:
            raise ValueError(f"Input material {path} has no video or image tracks")

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

        if not pymediainfo.MediaInfo.can_parse():
            raise ValueError("Unsupported audio material type %s" % os.path.splitext(path)[1])
        info: pymediainfo.MediaInfo = pymediainfo.MediaInfo.parse(path)  # type: ignore
        if len(info.video_tracks):
            raise ValueError("Audio materials should not contain video tracks")
        if not len(info.audio_tracks):
            raise ValueError(f"Given material file {path} has no audio tracks")
        self.duration = int(info.audio_tracks[0].duration * 1e3)  # type: ignore

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
