from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SubtitleLine:
    index: int
    start_ms: int
    end_ms: int
    content: str


@dataclass
class ClipManifest:
    index: int
    segment_id: str
    start_ms: int
    end_ms: int
    voice: str
    rate: str
    pitch: str
    volume: str
    translated_text: str
    spoken_text: str
    delivery: str
    clip_ms: int
    target_ms: int
    fitted_path: str
    reference_energy_db: float | None = None
    dub_energy_db: float | None = None
    energy_gain_db: float = 0.0
