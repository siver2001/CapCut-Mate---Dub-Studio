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
from ..render_utils import (
    compose_ass,
    default_subtitle_region,
    effective_ass_font_size,
    effective_ass_margin_v,
    effective_ass_outline,
    hex_to_ass_color,
    resolve_subtitle_region_for_position,
)
from ..subtitle_utils import (
    apply_subtitle_timeline_to_segments,
    build_subtitle_timeline,
    collapse_repeated_words,
    compose_srt,
    compose_srt_from_timeline,
    create_display_subtitles,
    looks_like_untranslated_source,
    merge_short_subtitles,
    normalize_first_person_pronouns,
    normalize_tts_period_pauses,
    normalize_text,
    parse_srt,
    parse_srt_to_timeline,
    pick_best_localized_text,
    prefer_minh_cau_pair,
    split_display_text,
    split_subtitle_lines_for_display,
    subtitle_timeline_to_lines,
)


STABLE_AUDIO_SAMPLE_RATE = 48000
STABLE_AUDIO_CHANNELS = 2


def stable_audio_filter_chain(*, trim_boundaries: bool = False) -> str:
    filters: list[str] = []
    if trim_boundaries:
        filters.append(
            "silenceremove="
            "start_periods=1:start_duration=0.03:start_threshold=-48dB:start_silence=0.02"
        )
    filters.append("aresample=async=1:min_hard_comp=0.100:first_pts=0")
    filters.append("asetpts=N/SR/TB")
    return ",".join(filters)
