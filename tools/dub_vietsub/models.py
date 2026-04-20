from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ClipManifest:
    index: int
    start_ms: int
    end_ms: int
    voice: str
    rate: str
    original_text: str
    translated_text: str
    clip_ms: int
    target_ms: int
