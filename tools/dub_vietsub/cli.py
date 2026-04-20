from __future__ import annotations

import argparse
from pathlib import Path

from .audio import create_dub_audio, mix_audio
from .config import DEFAULT_VOICES, MODEL_PATH, ROOT, TEMP_DIR
from .io_utils import ensure_workspace, load_manual_lines, load_srt, save_srt, write_manifest
from .render import burn_subtitles
from .subtitles import (
    build_vietnamese_subtitles,
    merge_short_subtitles,
    transcribe_to_srt,
)
from .translate import translate_lines


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create Vietnamese dub and subtitles for a source video.")
    parser.add_argument("--input", required=True, help="Path to the source video.")
    parser.add_argument(
        "--output",
        help="Path to the final exported video. Defaults to <input>_vietsub_dub.mp4 in the project root.",
    )
    parser.add_argument(
        "--voices",
        nargs="+",
        default=DEFAULT_VOICES,
        help="Vietnamese Edge TTS voices to cycle through.",
    )
    parser.add_argument(
        "--subtitle-source",
        choices=["merged", "raw"],
        default="merged",
        help="Use merged sentence-level subtitles or the raw transcription fragments.",
    )
    parser.add_argument(
        "--manual-translation-file",
        help="Optional UTF-8 text file with one Vietnamese sentence per line.",
    )
    parser.add_argument(
        "--keep-original-audio",
        action="store_true",
        help="Keep the original audio quietly under the Vietnamese dub.",
    )
    parser.add_argument(
        "--cover-source-subtitles",
        action="store_true",
        help="Mask the hardcoded source subtitles near the bottom of the frame.",
    )
    parser.add_argument(
        "--subtitle-font-size",
        type=int,
        default=18,
        help="Burned subtitle font size.",
    )
    parser.add_argument(
        "--wrap-width",
        type=int,
        default=24,
        help="Approximate line wrap width for Vietnamese subtitles.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ensure_workspace()

    video_path = Path(args.input).resolve()
    if not video_path.exists():
        raise FileNotFoundError(f"Input video not found: {video_path}")
    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Whisper model not found: {MODEL_PATH}")

    output_path = Path(args.output).resolve() if args.output else ROOT / f"{video_path.stem}_vietsub_dub.mp4"
    raw_srt_path = TEMP_DIR / "original_transcription.srt"
    merged_srt_path = TEMP_DIR / "original_transcription_merged.srt"
    vietnamese_srt_path = TEMP_DIR / "vietnamese_subtitles.srt"

    print("Step 1/5: Transcribing source audio...")
    if raw_srt_path.exists() and raw_srt_path.stat().st_size > 0:
        print(f"Reusing existing transcription: {raw_srt_path}")
    else:
        transcribe_to_srt(video_path, raw_srt_path)

    print("Step 2/5: Preparing subtitle segments...")
    raw_subtitles = load_srt(raw_srt_path)
    merged_subtitles = merge_short_subtitles(raw_subtitles)
    save_srt(merged_srt_path, merged_subtitles)
    source_subtitles = merged_subtitles if args.subtitle_source == "merged" else raw_subtitles

    print("Step 3/5: Translating to Vietnamese...")
    if args.manual_translation_file:
        manual_path = Path(args.manual_translation_file).resolve()
        translated_lines = load_manual_lines(manual_path)
        if len(translated_lines) != len(source_subtitles):
            raise ValueError(
                f"Manual translation line count mismatch: expected {len(source_subtitles)}, got {len(translated_lines)}"
            )
    else:
        translated_lines = translate_lines([item.content for item in source_subtitles])
    vietnamese_subtitles = build_vietnamese_subtitles(
        source_subtitles,
        translated_lines,
        wrap_width=args.wrap_width,
    )
    save_srt(vietnamese_srt_path, vietnamese_subtitles)

    print("Step 4/5: Generating Vietnamese dub...")
    dub_audio_path, manifest = create_dub_audio(video_path, vietnamese_subtitles, translated_lines, args.voices)
    write_manifest(manifest)

    print("Step 5/5: Mixing audio and exporting final video...")
    mixed_audio_path = mix_audio(video_path, dub_audio_path, keep_original_audio=args.keep_original_audio)
    burn_subtitles(
        video_path,
        mixed_audio_path,
        vietnamese_srt_path,
        output_path,
        cover_source_subtitles=args.cover_source_subtitles,
        subtitle_font_size=args.subtitle_font_size,
    )

    print(f"Done. Final video: {output_path}")
    print(f"Vietnamese subtitles: {vietnamese_srt_path}")
    return 0
