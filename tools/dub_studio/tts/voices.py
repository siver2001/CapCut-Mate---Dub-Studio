from __future__ import annotations

from pathlib import Path
import threading
import time

from ..cli_parts.analysis import resolve_edge_voice_name, resolve_voice_preset


class EdgeVoiceHealthRegistry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._healthy: set[str] = set()
        self._unhealthy: dict[str, str] = {}
        self._transient_failures: dict[str, int] = {}
        self._blocked_until: dict[str, float] = {}

    def mark_healthy(self, voice: str) -> None:
        with self._lock:
            self._healthy.add(voice)
            self._unhealthy.pop(voice, None)
            self._transient_failures.pop(voice, None)
            self._blocked_until.pop(voice, None)

    def mark_unhealthy(self, voice: str, reason: str) -> None:
        with self._lock:
            self._healthy.discard(voice)
            self._unhealthy[voice] = reason
            self._blocked_until[voice] = max(
                self._blocked_until.get(voice, 0.0),
                time.monotonic() + 600.0,
            )

    def is_unhealthy(self, voice: str) -> bool:
        with self._lock:
            blocked_until = self._blocked_until.get(voice, 0.0)
            if blocked_until and blocked_until <= time.monotonic():
                self._blocked_until.pop(voice, None)
                self._transient_failures.pop(voice, None)
                self._unhealthy.pop(voice, None)
                return False
            return blocked_until > time.monotonic() or voice in self._unhealthy

    def mark_transient_failure(self, voice: str, *, cooldown_seconds: float = 180.0) -> None:
        with self._lock:
            failures = self._transient_failures.get(voice, 0) + 1
            self._transient_failures[voice] = failures
            if failures >= 8:
                self._healthy.discard(voice)
                self._unhealthy[voice] = "Repeated Edge TTS no-audio responses"
                self._blocked_until[voice] = max(
                    self._blocked_until.get(voice, 0.0),
                    time.monotonic() + max(float(cooldown_seconds), 180.0),
                )

    def transient_failure_count(self, voice: str) -> int:
        with self._lock:
            return self._transient_failures.get(voice, 0)

    def filter_candidates(self, voices: list[str]) -> list[str]:
        filtered = [voice for voice in voices if not self.is_unhealthy(voice)]
        return filtered or voices


EDGE_VOICE_HEALTH = EdgeVoiceHealthRegistry()

EDGE_VOICE_FALLBACKS: dict[str, list[str]] = {
    "vi-VN-NamMinhNeural": ["vi-VN-HoaiMyNeural"],
    "vi-VN-HoaiMyNeural": ["vi-VN-NamMinhNeural"],
}


def resolve_edge_voice_candidates(candidate: str) -> list[str]:
    primary_voice = resolve_edge_voice_name(candidate)
    if not primary_voice:
        return []
    candidates = [primary_voice, *EDGE_VOICE_FALLBACKS.get(primary_voice, [])]
    unique_candidates: list[str] = []
    seen: set[str] = set()
    for voice_name in candidates:
        if voice_name and voice_name not in seen:
            seen.add(voice_name)
            unique_candidates.append(voice_name)
    return EDGE_VOICE_HEALTH.filter_candidates(unique_candidates)


def preflight_edge_voice(
    voice: str,
    *,
    output_dir: Path,
    save_audio,
    validate_audio,
    safe_print,
) -> bool:
    resolved = resolve_edge_voice_name(voice) or resolve_voice_preset(voice) or voice
    output_dir.mkdir(parents=True, exist_ok=True)
    probe_path = output_dir / f"preflight_{resolved.replace('-', '_')}.mp3"
    try:
        if not probe_path.exists() or probe_path.stat().st_size <= 0:
            save_audio(
                "Xin chao, day la kiem tra giong noi.",
                resolved,
                "+0%",
                probe_path,
                pitch="+0Hz",
                volume="+0%",
                use_boundary=False,
            )
        validate_audio(probe_path, context=f"Edge TTS preflight {resolved}")
        EDGE_VOICE_HEALTH.mark_healthy(resolved)
        safe_print(f"[tts] voice preflight ok: {resolved}", flush=True)
        return True
    except Exception as exc:
        EDGE_VOICE_HEALTH.mark_unhealthy(resolved, str(exc))
        safe_print(f"[tts] voice preflight failed: {resolved}: {exc}", flush=True)
        return False
