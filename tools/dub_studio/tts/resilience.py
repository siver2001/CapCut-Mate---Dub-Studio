from __future__ import annotations

import threading
import time


EDGE_TTS_CLI_FALLBACK_ERRORS = (
    "No audio was received",
    "NoAudioReceived",
    "TimeoutError",
    "WebSocket",
    "Server disconnected",
)


class TtsRateLimiter:
    def __init__(self, *, min_gap_seconds: float) -> None:
        self.min_gap_seconds = max(float(min_gap_seconds), 0.0)
        self._lock = threading.Lock()
        self._last_request_at = 0.0

    def run(self, callback):
        with self._lock:
            # Check for global cooldown
            current_time = time.monotonic()
            elapsed = current_time - self._last_request_at

            # Adaptive gap: increase gap if we've had recent errors
            effective_gap = self.min_gap_seconds
            if hasattr(self, "_backoff_until") and self._backoff_until > current_time:
                effective_gap *= 4.0

            if elapsed < effective_gap:
                # Add a bit of random jitter (0-800ms) to avoid perfectly regular patterns
                # that Microsoft's firewalls might flag.
                import random
                jitter = random.uniform(0, 0.8)
                sleep_time = (effective_gap - elapsed) + jitter
                time.sleep(sleep_time)

            try:
                return callback()
            finally:
                self._last_request_at = time.monotonic()

    def trigger_backoff(self, duration: float = 120.0):
        with self._lock:
            self._backoff_until = time.monotonic() + duration


def should_retry_edge_tts_with_cli(error: Exception) -> bool:
    message = f"{type(error).__name__}: {error}"
    return any(marker in message for marker in EDGE_TTS_CLI_FALLBACK_ERRORS)


def is_edge_no_audio_error(error: Exception | str) -> bool:
    try:
        from edge_tts.exceptions import NoAudioReceived

        if isinstance(error, NoAudioReceived):
            return True
    except ImportError:
        pass
    return "No audio was received" in str(error or "") or "NoAudioReceived" in str(error or "")


def is_edge_drm_error(error: Exception | str) -> bool:
    try:
        from edge_tts.exceptions import SkewAdjustmentError

        if isinstance(error, SkewAdjustmentError):
            return True
    except ImportError:
        pass
    return "SkewAdjustment" in str(error or "") or "403" in str(error or "")


def retry_sleep_seconds(attempt: int, *, no_audio: bool = False) -> float:
    base = 4.0 if no_audio else 3.5
    return base * max(attempt + 1, 1)

