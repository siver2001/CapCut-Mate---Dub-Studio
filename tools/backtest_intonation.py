from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import librosa
import numpy as np
from loguru import logger

sys.path.append(str(Path(__file__).parents[1]))

from tools.dub_studio_pipeline import (  # noqa: E402
    DEFAULT_VOICES,
    DUB_STUDIO_DIR,
    build_tts_delivery_profile,
    ensure_dir,
    estimate_rate,
    extract_audio_clip,
    fit_audio_length_with_mode,
    normalize_text,
    read_json,
    synthesize_tts,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backtest energy and rhythm similarity for dubbed clips.")
    parser.add_argument("--job-id", required=True, help="Dub Studio job ID.")
    parser.add_argument("--video", required=True, help="Source video path.")
    parser.add_argument("--analysis", default="", help="Optional explicit analysis JSON path.")
    parser.add_argument("--limit", type=int, default=6, help="Number of segments to test.")
    parser.add_argument("--timing-mode", default="balanced_natural", help="Timing mode for fitting the TTS clip.")
    parser.add_argument(
        "--output",
        default="",
        help="Optional output JSON path. Defaults to temp/dub_studio/<job>/analysis/backtest_intonation.json",
    )
    return parser.parse_args()


def load_audio(audio_path: Path, sr: int = 16000) -> tuple[np.ndarray, int]:
    audio, sample_rate = librosa.load(str(audio_path), sr=sr, mono=True)
    return audio.astype(np.float32), sample_rate


def resample_signature(values: np.ndarray, bins: int = 64) -> np.ndarray:
    if values.size == 0:
        return np.zeros(bins, dtype=np.float32)
    if values.size == 1:
        return np.repeat(values.astype(np.float32), bins)
    source = np.linspace(0.0, 1.0, num=values.size)
    target = np.linspace(0.0, 1.0, num=bins)
    return np.interp(target, source, values).astype(np.float32)


def compute_metrics(audio_path: Path) -> dict[str, float]:
    audio, sr = load_audio(audio_path)
    if audio.size == 0:
        return {
            "durationMs": 0.0,
            "rmsDb": -120.0,
            "pauseRatio": 1.0,
            "peak": 0.0,
            "rhythmStd": 0.0,
        }

    frame_length = int(sr * 0.04)
    hop_length = int(sr * 0.02)
    rms = librosa.feature.rms(y=audio, frame_length=frame_length, hop_length=hop_length)[0]
    rms_db = 20.0 * math.log10(max(float(np.sqrt(np.mean(np.square(audio, dtype=np.float64)))), 1e-6))
    peak = float(np.max(np.abs(audio)))
    pause_floor = max(float(np.median(rms)) * 0.35, 0.008)
    pause_ratio = float(np.mean(rms <= pause_floor))
    rhythm_std = float(np.std(resample_signature(rms, bins=64)))
    return {
        "durationMs": float((audio.size / sr) * 1000.0),
        "rmsDb": float(rms_db),
        "pauseRatio": pause_ratio,
        "peak": peak,
        "rhythmStd": rhythm_std,
    }


def rhythm_similarity(reference_path: Path, candidate_path: Path) -> float:
    reference_audio, sr = load_audio(reference_path)
    candidate_audio, _ = load_audio(candidate_path, sr=sr)
    frame_length = int(sr * 0.04)
    hop_length = int(sr * 0.02)
    reference_rms = librosa.feature.rms(y=reference_audio, frame_length=frame_length, hop_length=hop_length)[0]
    candidate_rms = librosa.feature.rms(y=candidate_audio, frame_length=frame_length, hop_length=hop_length)[0]
    a = resample_signature(reference_rms, bins=64)
    b = resample_signature(candidate_rms, bins=64)
    a = a / max(float(np.linalg.norm(a)), 1e-6)
    b = b / max(float(np.linalg.norm(b)), 1e-6)
    return float(np.clip(np.dot(a, b), 0.0, 1.0))


def score_result(reference: dict[str, float], candidate: dict[str, float], rhythm: float) -> dict[str, float]:
    energy_delta = abs(candidate["rmsDb"] - reference["rmsDb"])
    duration_ratio = candidate["durationMs"] / max(reference["durationMs"], 1.0)
    pause_delta = abs(candidate["pauseRatio"] - reference["pauseRatio"])
    energy_score = max(0.0, 1.0 - min(energy_delta / 8.0, 1.0))
    duration_score = max(0.0, 1.0 - min(abs(duration_ratio - 1.0) / 0.45, 1.0))
    pause_score = max(0.0, 1.0 - min(pause_delta / 0.35, 1.0))
    total = (energy_score * 0.35) + (rhythm * 0.35) + (duration_score * 0.2) + (pause_score * 0.1)
    return {
        "energyDeltaDb": round(energy_delta, 3),
        "durationRatio": round(duration_ratio, 3),
        "pauseDelta": round(pause_delta, 3),
        "rhythmSimilarity": round(rhythm, 3),
        "score": round(total * 100.0, 2),
    }


def select_segments(analysis: dict[str, object], limit: int) -> list[dict[str, object]]:
    segments = list(analysis.get("segments") or [])
    ranked = sorted(
        segments,
        key=lambda item: (
            len(normalize_text(item.get("spokenText") or item.get("translatedText") or item.get("sourceText") or "")),
            max(int(item.get("endMs", 0)) - int(item.get("startMs", 0)), 0),
        ),
        reverse=True,
    )
    return ranked[: max(limit, 1)]


def synthesize_backtest_clip(
    *,
    segment: dict[str, object],
    voice_mapping: dict[str, str],
    job_id: str,
    timing_mode: str,
    work_dir: Path,
) -> Path:
    text = normalize_text(segment.get("spokenText") or segment.get("translatedText") or segment.get("sourceText") or "")
    if not text:
        raise RuntimeError(f"Segment {segment.get('id')} has no text to synthesize.")

    speaker_id = str(segment.get("speakerId") or "speaker_1")
    voice = voice_mapping.get(speaker_id) or DEFAULT_VOICES[0]
    delivery = normalize_text(segment.get("delivery") or "neutral").lower() or "neutral"
    profile = build_tts_delivery_profile(
        text=text,
        source_text=str(segment.get("sourceText") or text),
        voice=voice,
        delivery=delivery,
    )
    target_ms = max(int(segment.get("endMs", 0)) - int(segment.get("startMs", 0)), 500)
    rate = estimate_rate(profile["spokenText"], target_ms, timing_mode=timing_mode)

    raw_path = work_dir / f"{segment['id']}_raw.wav"
    fitted_path = work_dir / f"{segment['id']}_fitted.wav"
    synthesize_tts(
        text=profile["spokenText"],
        voice=voice,
        rate=rate,
        output_path=raw_path,
        pitch=profile["pitch"],
        volume=profile["volume"],
        job_id=job_id,
        speaker_id=speaker_id,
    )
    fit_audio_length_with_mode(raw_path, fitted_path, target_ms, timing_mode)
    return fitted_path


def run_backtest(job_id: str, video_path: Path, analysis_path: Path, limit: int, timing_mode: str, output_path: Path) -> dict[str, object]:
    logger.info(f"Backtesting dubbing pipeline for job={job_id}")
    analysis = read_json(analysis_path)
    voice_mapping = analysis.get("renderDefaults", {}).get("voiceMapping", {}) or {}
    segments = select_segments(analysis, limit)
    if not segments:
        raise RuntimeError("No segments found in analysis JSON.")

    job_dir = DUB_STUDIO_DIR / job_id
    work_dir = ensure_dir(job_dir / "backtest")
    results: list[dict[str, object]] = []

    for segment in segments:
        seg_id = str(segment["id"])
        try:
            reference_path = work_dir / f"{seg_id}_reference.wav"
            duration_ms = max(int(segment.get("endMs", 0)) - int(segment.get("startMs", 0)), 250)
            extract_audio_clip(video_path, reference_path, int(segment.get("startMs", 0)), duration_ms)
            candidate_path = synthesize_backtest_clip(
                segment=segment,
                voice_mapping=voice_mapping,
                job_id=job_id,
                timing_mode=timing_mode,
                work_dir=work_dir,
            )

            reference_metrics = compute_metrics(reference_path)
            candidate_metrics = compute_metrics(candidate_path)
            rhythm = rhythm_similarity(reference_path, candidate_path)
            score = score_result(reference_metrics, candidate_metrics, rhythm)
            results.append(
                {
                    "segmentId": seg_id,
                    "speakerId": segment.get("speakerId") or "speaker_1",
                    "sourceText": segment.get("sourceText") or "",
                    "spokenText": segment.get("spokenText") or segment.get("translatedText") or "",
                    "referencePath": str(reference_path),
                    "candidatePath": str(candidate_path),
                    "reference": reference_metrics,
                    "candidate": candidate_metrics,
                    "status": "ok",
                    **score,
                }
            )
        except Exception as exc:
            logger.error(f"Backtest failed for segment {seg_id}: {exc}")
            results.append(
                {
                    "segmentId": seg_id,
                    "speakerId": segment.get("speakerId") or "speaker_1",
                    "sourceText": segment.get("sourceText") or "",
                    "spokenText": segment.get("spokenText") or segment.get("translatedText") or "",
                    "status": "error",
                    "error": str(exc),
                    "score": 0.0,
                }
            )

    average_score = round(sum(float(item["score"]) for item in results) / len(results), 2)
    summary = {
        "jobId": job_id,
        "videoPath": str(video_path),
        "analysisPath": str(analysis_path),
        "testedSegments": len(results),
        "averageScore": average_score,
        "timingMode": timing_mode,
        "results": results,
    }
    output_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"Backtest complete. Average score={average_score}")
    return summary


def main() -> int:
    args = parse_args()
    video_path = Path(args.video).expanduser().resolve()
    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")

    job_dir = DUB_STUDIO_DIR / args.job_id
    default_analysis = job_dir / "analysis.json"
    fallback_analysis = job_dir / "analysis" / "analysis.json"
    analysis_path = Path(args.analysis).expanduser().resolve() if args.analysis else (default_analysis if default_analysis.exists() else fallback_analysis)
    if not analysis_path.exists():
        raise FileNotFoundError(f"Analysis JSON not found: {analysis_path}")

    output_path = (
        Path(args.output).expanduser().resolve()
        if args.output
        else job_dir / "analysis" / "backtest_intonation.json"
    )
    ensure_dir(output_path.parent)
    run_backtest(args.job_id, video_path, analysis_path, args.limit, args.timing_mode, output_path)
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
