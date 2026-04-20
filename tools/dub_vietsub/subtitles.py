from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import Iterable

import srt

from .config import MODEL_PATH, ROOT
from .io_utils import run
from .text import normalize_text, split_display_text, wrap_vietnamese_text


def merge_short_subtitles(subtitles: Iterable[srt.Subtitle]) -> list[srt.Subtitle]:
    merged: list[srt.Subtitle] = []
    current: srt.Subtitle | None = None

    for raw in subtitles:
        content = normalize_text(raw.content)
        if not content:
            continue

        item = srt.Subtitle(index=raw.index, start=raw.start, end=raw.end, content=content)
        if current is None:
            current = item
            continue

        current_span = (current.end - current.start).total_seconds()
        merged_span = (item.end - current.start).total_seconds()
        gap = (item.start - current.end).total_seconds()
        combined_len = len(f"{current.content} {item.content}")
        if (
            gap <= 0.55
            and merged_span <= 6.5
            and (current_span < 3.5 or len(current.content) < 42)
            and combined_len <= 110
        ):
            current = srt.Subtitle(
                index=current.index,
                start=current.start,
                end=item.end,
                content=f"{current.content} {item.content}",
            )
            continue

        merged.append(current)
        current = item

    if current is not None:
        merged.append(current)

    for idx, item in enumerate(merged, start=1):
        item.index = idx
    return merged


def transcribe_to_srt(video_path: Path, output_srt: Path) -> None:
    relative_model = MODEL_PATH.relative_to(ROOT).as_posix()
    relative_srt = output_srt.relative_to(ROOT).as_posix()
    whisper_filter = (
        f"whisper=model={relative_model}:language=zh:use_gpu=false:format=srt:"
        f"destination={relative_srt}:max_len=32"
    )
    run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(video_path),
            "-vn",
            "-af",
            whisper_filter,
            "-f",
            "null",
            "-",
        ],
        cwd=ROOT,
    )


def build_vietnamese_subtitles(
    original: list[srt.Subtitle],
    translated_lines: list[str],
    wrap_width: int = 24,
) -> list[srt.Subtitle]:
    vietnamese: list[srt.Subtitle] = []
    for idx, (source, translated) in enumerate(zip(original, translated_lines), start=1):
        vietnamese.append(
            srt.Subtitle(
                index=idx,
                start=source.start,
                end=source.end,
                content=wrap_vietnamese_text(translated, width=wrap_width),
            )
        )
    return vietnamese


def build_display_subtitles(
    subtitles: list[srt.Subtitle],
    max_words: int = 5,
    max_chars: int = 22,
) -> list[srt.Subtitle]:
    display_subtitles: list[srt.Subtitle] = []
    index = 1

    for subtitle in subtitles:
        chunks = split_display_text(subtitle.content, max_words=max_words, max_chars=max_chars)
        if not chunks:
            continue

        start_seconds = subtitle.start.total_seconds()
        end_seconds = subtitle.end.total_seconds()
        total_seconds = max(end_seconds - start_seconds, 0.4)
        weights = [max(len(chunk.replace(" ", "")), 1) for chunk in chunks]
        total_weight = sum(weights)
        cursor = start_seconds

        for chunk, weight in zip(chunks, weights):
            duration = total_seconds * (weight / total_weight)
            chunk_end = min(end_seconds, cursor + duration)
            display_subtitles.append(
                srt.Subtitle(
                    index=index,
                    start=timedelta(seconds=cursor),
                    end=timedelta(seconds=max(chunk_end, cursor + 0.12)),
                    content=chunk,
                )
            )
            index += 1
            cursor = chunk_end

        display_subtitles[-1].end = timedelta(seconds=end_seconds)

    for current, following in zip(display_subtitles, display_subtitles[1:]):
        if current.end > following.start:
            current.end = max(current.start + timedelta(milliseconds=120), following.start)

    return display_subtitles
