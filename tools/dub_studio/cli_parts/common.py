from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
from contextlib import contextmanager
from functools import lru_cache
import time
import urllib.parse
import urllib.request
from dataclasses import asdict
from pathlib import Path
from typing import Any

import requests

from ..config import *  # noqa: F401,F403
from ..io_utils import read_json, write_json
from ..media_utils import (
    extract_audio_for_whisperx,
    extract_gray_frame,
    extract_thumbnail,
    ffprobe_audio_duration_ms,
    ffprobe_duration_ms,
    get_video_meta,
    validate_generated_audio_file,
)
from ..models import ClipManifest, SubtitleLine
from ..process_utils import (
    emit,
    emit_progress,
    ensure_dir,
    ensure_job_dirs,
    ensure_python_packages,
    extract_audio_clip,
    run,
    run_output,
    safe_print,
)
from ..render_utils import compose_ass, default_subtitle_region, resolve_subtitle_region_for_position
from ..subtitle_utils import (
    apply_subtitle_timeline_to_segments,
    build_subtitle_timeline,
    build_spoken_text,
    collapse_repeated_words,
    compose_srt,
    compose_srt_from_timeline,
    create_display_subtitles,
    merge_short_subtitles,
    normalize_first_person_pronouns,
    normalize_tts_period_pauses,
    normalize_text,
    parse_srt,
    parse_srt_to_timeline,
    prefer_minh_cau_pair,
    split_display_text,
    subtitle_timeline_to_lines,
)
