from __future__ import annotations

from .common import *

def ensure_local_whisper_model(*, phase: str, step: str, progress: float) -> Path:
    existing = [candidate for candidate in MODEL_CANDIDATES if candidate.exists()]
    if existing:
        return max(existing, key=lambda path: path.stat().st_size)
    ensure_python_packages(
        [("huggingface_hub", "huggingface_hub")],
        phase=phase,
        step=step,
        progress=max(progress - 0.01, 0.0),
        message="Đang cài huggingface_hub để tải model ffmpeg-whisper offline...",
    )
    emit_progress(
        phase=phase,
        step=step,
        progress=progress,
        message=f"Đang tải model offline {WHISPER_CPP_MODEL_FILENAME} cho ffmpeg-whisper...",
    )
    from huggingface_hub import hf_hub_download  # type: ignore

    models_dir = ensure_dir(ROOT / "temp" / "models")
    try:
        downloaded = hf_hub_download(
            repo_id=WHISPER_CPP_MODEL_REPO,
            filename=WHISPER_CPP_MODEL_FILENAME,
            local_dir=str(models_dir),
            local_dir_use_symlinks=False,
        )
    except TypeError:
        downloaded = hf_hub_download(
            repo_id=WHISPER_CPP_MODEL_REPO,
            filename=WHISPER_CPP_MODEL_FILENAME,
            local_dir=str(models_dir),
        )
    return Path(downloaded)


def get_transcription_model_path() -> Path:
    return ensure_local_whisper_model(phase="analysis", step="prepare", progress=0.03)





def hf_repo_cache_dir(repo_id: str) -> Path:
    normalized = normalize_text(repo_id)
    return HUGGINGFACE_HUB_CACHE / f"models--{normalized.replace('/', '--')}"


def hf_repo_snapshots(repo_id: str) -> list[Path]:
    snapshots_dir = hf_repo_cache_dir(repo_id) / "snapshots"
    if not snapshots_dir.exists():
        return []
    return sorted((item for item in snapshots_dir.iterdir() if item.is_dir()), key=lambda path: path.stat().st_mtime)


def hf_repo_cached(repo_id: str) -> bool:
    return bool(repo_id) and bool(hf_repo_snapshots(repo_id))


def ensure_hf_snapshot(
    repo_id: str,
    *,
    phase: str,
    step: str,
    progress: float,
    message: str,
    allow_patterns: list[str] | None = None,
    token: str = "",
) -> Path | None:
    normalized = normalize_text(repo_id)
    if not normalized:
        return None
    snapshots = hf_repo_snapshots(normalized)
    if snapshots:
        return snapshots[-1]
    ensure_python_packages(
        [("huggingface_hub", "huggingface_hub")],
        phase=phase,
        step=step,
        progress=max(progress - 0.01, 0.0),
        message="Đang cài huggingface_hub để tải model WhisperX...",
    )
    emit_progress(
        phase=phase,
        step=step,
        progress=progress,
        message=message,
    )
    from huggingface_hub import snapshot_download  # type: ignore

    repo_cache_dir = hf_repo_cache_dir(normalized)
    local_snapshot_dir = repo_cache_dir / "snapshots" / "local"
    local_snapshot_dir.mkdir(parents=True, exist_ok=True)
    kwargs: dict[str, Any] = {
        "repo_id": normalized,
        "cache_dir": str(HUGGINGFACE_HUB_CACHE),
        "local_dir": str(local_snapshot_dir),
    }
    kwargs["local_dir_use_symlinks"] = False
    if allow_patterns:
        kwargs["allow_patterns"] = allow_patterns
    if token:
        kwargs["token"] = token
    try:
        with temporarily_disable_dead_local_proxies(), temporarily_use_workspace_hf_home():
            snapshot_download(**kwargs)
    except Exception as exc:
        message = normalize_text(str(exc))
        if "gated repo" in message.lower() or "authorized list" in message.lower():
            raise RuntimeError(
                f"Model {normalized} đang là gated repo trên Hugging Face. Hãy đăng nhập đúng tài khoản HF đã có token và bấm chấp nhận quyền truy cập trên trang model rồi chạy lại."
            ) from exc
        raise
    snapshots = hf_repo_snapshots(normalized)
    return snapshots[-1] if snapshots else None


def whisperx_asr_repo_id(model_name: str) -> str:
    normalized = normalize_text(model_name)
    if not normalized:
        return ""
    if "/" in normalized:
        return normalized
    aliases = {
        "distil-large-v3": "distil-whisper/distil-large-v3",
        "large-v3": "Systran/faster-whisper-large-v3",
        "large-v2": "Systran/faster-whisper-large-v2",
        "medium": "Systran/faster-whisper-medium",
        "small": "Systran/faster-whisper-small",
        "base": "Systran/faster-whisper-base",
        "tiny": "Systran/faster-whisper-tiny",
    }
    return aliases.get(normalized, f"Systran/faster-whisper-{normalized}")


def whisperx_align_repo_id(language_code: str) -> str:
    normalized = normalize_text(language_code).lower()
    if not normalized:
        return ""
    candidates = [normalized]
    short_code = normalized.split("-", 1)[0]
    if short_code not in candidates:
        candidates.append(short_code)
    try:
        alignment_module = importlib.import_module("whisperx.alignment")
        default_models = getattr(alignment_module, "DEFAULT_ALIGN_MODELS_HF", {}) or {}
    except Exception:
        default_models = {}
    for code in candidates:
        repo_id = normalize_text(default_models.get(code) or "")
        if repo_id:
            return repo_id
    fallback_models = {
        "ja": "jonatasgrosman/wav2vec2-large-xlsr-53-japanese",
        "zh": "jonatasgrosman/wav2vec2-large-xlsr-53-chinese-zh-cn",
        "ko": "kresnik/wav2vec2-large-xlsr-korean",
        "vi": "nguyenvulebinh/wav2vec2-base-vi-vlsp2020",
    }
    for code in candidates:
        repo_id = fallback_models.get(code)
        if repo_id:
            return repo_id
    return ""


def ensure_whisperx_model_cache(*, phase: str, step: str, progress: float) -> None:
    repo_id = WHISPERX_ASR_REPO or whisperx_asr_repo_id(WHISPERX_MODEL)
    if not repo_id:
        return
    ensure_hf_snapshot(
        repo_id,
        phase=phase,
        step=step,
        progress=progress,
        message=f"Đang tải model WhisperX {WHISPERX_MODEL} vào cache local...",
    )


def ensure_whisperx_align_cache(*, language_code: str, phase: str, step: str, progress: float) -> str:
    repo_id = whisperx_align_repo_id(language_code)
    if not repo_id:
        return ""
    ensure_hf_snapshot(
        repo_id,
        phase=phase,
        step=step,
        progress=progress,
        message=f"Đang tải model căn chỉnh WhisperX cho ngôn ngữ {language_code}...",
    )
    return repo_id


def ensure_whisperx_diarization_cache(*, phase: str, step: str, progress: float) -> str:
    repo_id = normalize_text(WHISPERX_DIARIZATION_MODEL)
    hf_token = resolve_hf_token()
    if not repo_id or not hf_token:
        return ""
    ensure_hf_snapshot(
        repo_id,
        phase=phase,
        step=step,
        progress=progress,
        message="Đang tải model diarization WhisperX vào cache local...",
        token=hf_token,
    )
    return repo_id


def discover_ollama_binary() -> Path | None:
    candidates: list[Path] = []
    if OLLAMA_BIN:
        candidates.append(Path(OLLAMA_BIN).expanduser())
    resolved = shutil.which("ollama")
    if resolved:
        candidates.append(Path(resolved))
    if sys.platform == "win32":
        candidates.extend(
            [
                Path(os.getenv("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe",
                Path("C:/Program Files/Ollama/ollama.exe"),
            ]
        )
    for candidate in candidates:
        if candidate and candidate.exists():
            return candidate
    return None


def ollama_tags() -> list[str]:
    try:
        req = urllib.request.Request(f"{OLLAMA_BASE_URL}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=4.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return [item.get("name", "") for item in data.get("models", [])]
    except Exception:
        return []


def ollama_running_models() -> list[str]:
    try:
        req = urllib.request.Request(f"{OLLAMA_BASE_URL}/api/ps", method="GET")
        with urllib.request.urlopen(req, timeout=4.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return [item.get("name", "") for item in data.get("models", [])]
    except Exception:
        return []


def ollama_model_loaded() -> bool:
    if not OLLAMA_MODEL:
        return False
    loaded_models = ollama_running_models()
    base_model = OLLAMA_MODEL.split(":")[0] if ":" in OLLAMA_MODEL else OLLAMA_MODEL
    return any(
        OLLAMA_MODEL == model
        or model.startswith(f"{OLLAMA_MODEL}:")
        or base_model == model.split(":")[0]
        for model in loaded_models
    )


def ollama_model_available() -> bool:
    if not OLLAMA_MODEL:
        return False
    models = ollama_tags()
    base_model = OLLAMA_MODEL.split(":")[0] if ":" in OLLAMA_MODEL else OLLAMA_MODEL
    return any(
        OLLAMA_MODEL == model
        or model.startswith(f"{OLLAMA_MODEL}:")
        or base_model == model.split(":")[0]
        for model in models
    )


def ensure_ollama_runtime(
    *,
    required: bool,
    phase: str,
    step: str,
    progress: float,
) -> bool:
    if not OLLAMA_MODEL:
        return False
    binary = discover_ollama_binary()
    if binary is None and required and sys.platform == "win32":
        emit_progress(
            phase=phase,
            step=step,
            progress=max(progress - 0.02, 0.0),
            message="Đang cài Ollama bằng winget...",
        )
        try:
            run(
                [
                    "winget",
                    "install",
                    OLLAMA_WINGET_ID,
                    "--accept-source-agreements",
                    "--accept-package-agreements",
                    "--silent",
                ]
            )
        except Exception as exc:
            raise RuntimeError(f"Khong the tu dong cai Ollama: {exc}") from exc
        binary = discover_ollama_binary()
    if binary is None:
        return False
    try:
        if ollama_model_available():
            return True
    except Exception:
        if required:
            creationflags = 0
            if sys.platform == "win32":
                creationflags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(
                    subprocess, "CREATE_NEW_PROCESS_GROUP", 0
                )
            try:
                subprocess.Popen(
                    [str(binary), "serve"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=creationflags,
                )
            except Exception:
                pass
            deadline = time.time() + 20
            while time.time() < deadline:
                try:
                    if ollama_model_available():
                        return True
                    break
                except Exception:
                    time.sleep(1)
        else:
            return False
    emit_progress(
        phase=phase,
        step=step,
        progress=progress,
        message=f"Đang tải model Ollama: {OLLAMA_MODEL}...",
    )
    try:
        # Model pull can take several minutes depending on internet speed.
        print(f"[info] Đang tải model {OLLAMA_MODEL} từ Ollama Hub (có thể mất vài phút)...", flush=True)
        run([str(binary), "pull", OLLAMA_MODEL], timeout=600.0)
    except Exception:
        return False
    try:
        return ollama_model_available()
    except Exception:
        return False


def discover_ollama() -> bool:
    return ensure_ollama_runtime(
        required=False,
        phase="analysis",
        step="prepare",
        progress=0.05,
    )


def should_use_ollama(provider: str) -> bool:
    """Determine if Ollama should be used based on the provider setting."""
    normalized = str(provider or "").strip().lower()
    if normalized == "ollama":
        if not ensure_ollama_runtime(
            required=True,
            phase="analysis",
            step="prepare",
            progress=0.05,
        ):
            raise RuntimeError(
                f"Da chon provider ollama nhung khong the ket noi Ollama tai {OLLAMA_BASE_URL} "
                f"hoac model '{OLLAMA_MODEL}' chua san sang."
            )
        return True
    if normalized == "auto":
        return discover_ollama()
    return False


def estimate_ollama_timeout(prompt: str, *, max_tokens: int, attempt: int = 0) -> int:
    retry_bonus = attempt * 15
    estimated = OLLAMA_TIMEOUT + retry_bonus
    return max(OLLAMA_TIMEOUT, min(estimated, OLLAMA_MAX_TIMEOUT))


def warmup_ollama_model(*, phase: str, progress: float) -> None:
    if not OLLAMA_WARMUP or not OLLAMA_MODEL:
        return
    if ollama_model_loaded():
        return
    emit_progress(
        phase=phase,
        step="translate",
        progress=progress,
        message=f"Đang warm-up model Ollama {OLLAMA_MODEL} để giảm timeout batch đầu...",
    )
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": "Trả lời đúng một từ: OK",
        "keep_alive": OLLAMA_KEEP_ALIVE or "30m",
        "options": {
            "num_ctx": OLLAMA_CTX,
            "num_predict": 8,
            "temperature": 0.0,
        },
    }
    result = _ollama_stream_generate(
        payload,
        connect_timeout=15.0,
        stall_timeout=float(OLLAMA_WARMUP_TIMEOUT),
    )
    if not result:
        raise RuntimeError(f"Ollama warm-up trả về payload không hợp lệ cho model {OLLAMA_MODEL}.")


def _ollama_stream_generate(payload: dict, *, connect_timeout: float = 15.0, stall_timeout: float = 60.0) -> str:
    """Stream tokens from Ollama and accumulate the full response.

    Instead of waiting for the entire generation with ``stream: False``,
    this reads the NDJSON stream token-by-token.  The connection only
    times out if no new chunk arrives within *stall_timeout* seconds,
    making it resilient to long generation times while still detecting
    genuine stalls quickly.
    """
    stream_payload = {**payload, "stream": True}
    url = f"{OLLAMA_BASE_URL}/api/generate"
    resp = requests.post(
        url,
        json=stream_payload,
        timeout=(connect_timeout, stall_timeout),
        stream=True,
    )
    resp.raise_for_status()

    fragments: list[str] = []
    done_reason = None
    for raw_line in resp.iter_lines(decode_unicode=True):
        if not raw_line:
            continue
        try:
            chunk = json.loads(raw_line)
        except json.JSONDecodeError:
            continue
            
        if chunk.get("error"):
            raise RuntimeError(f"Ollama API Error: {chunk['error']}")
            
        token = chunk.get("response", "")
        if token:
            fragments.append(token)
            
        if chunk.get("done"):
            done_reason = chunk.get("done_reason")
            break

    result = "".join(fragments).strip()
    if not result and done_reason:
        raise RuntimeError(f"Ollama ngừng đột ngột (lý do: {done_reason}). Có thể do hết VRAM hoặc vượt quá giới hạn ngữ cảnh (context length).")
    return result


def run_ollama_prompt(prompt: str, *, max_tokens: int = 2048, temperature: float | None = None, timeout: int | None = None) -> str:
    """Send a prompt to Ollama API and return the generated text with retries.

    Uses **streaming mode** so that the HTTP connection stays alive as
    long as tokens keep arriving.  A per-chunk stall timeout (default
    60 s) replaces the old single-shot socket timeout, eliminating the
    false-timeout failures with slow models like gemma4.
    """
    ensure_ollama_runtime(
        required=True,
        phase="render",
        step="prepare",
        progress=0.12,
    )
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "format": "json",
        "options": {
            "num_ctx": OLLAMA_CTX,
            "num_predict": max_tokens,
            "temperature": OLLAMA_TEMP if temperature is None else temperature,
        },
    }
    if OLLAMA_KEEP_ALIVE:
        payload["keep_alive"] = OLLAMA_KEEP_ALIVE

    # Stall timeout = how long we wait for *any* new token before giving up.
    # This replaces the old full-request timeout and is much more forgiving
    # for long generations while still catching genuine stalls.
    stall_timeout = float(timeout or estimate_ollama_timeout(prompt, max_tokens=max_tokens, attempt=0))
    # For streaming we mainly care about the stall, so cap it reasonably.
    stall_timeout = max(stall_timeout, 60.0)

    max_retries = 3
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        # Increase stall patience on retries
        effective_stall = stall_timeout + attempt * 30.0
        started_at = time.monotonic()
        print(
            f"[info] Đang gửi yêu cầu tới Ollama (lần {attempt + 1}, stall_timeout={effective_stall:.0f}s, stream=true)...",
            flush=True,
        )
        try:
            output = _ollama_stream_generate(
                payload,
                connect_timeout=15.0,
                stall_timeout=effective_stall,
            )
            if not output:
                raise RuntimeError("Ollama không trả về nội dung nào.")
            elapsed = time.monotonic() - started_at
            print(f"[info] Ollama hoàn tất trong {elapsed:.1f}s (JSON response: {len(output)} ký tự).", flush=True)
            return output
        except Exception as exc:
            last_exc = exc
            elapsed = time.monotonic() - started_at
            print(
                f"[warn] Ollama lỗi lần {attempt + 1}: {type(exc).__name__}: "
                f"{str(exc)[:200]} (sau {elapsed:.1f}s)",
                flush=True,
            )
            if attempt < max_retries:
                backoff = min(3.0 * (attempt + 1), 10.0)
                time.sleep(backoff)
                continue
            raise RuntimeError(
                f"Ollama request thất bại sau {elapsed:.1f}s "
                f"(thử {attempt + 1}/{max_retries + 1}, model={OLLAMA_MODEL})."
            ) from last_exc
    return ""


def iter_translation_batches(
    segments: list[dict[str, Any]],
    *,
    batch_size: int,
    first_batch_size: int | None = None,
):
    size = max(batch_size, 1)
    first_size = max(first_batch_size or size, 1)
    start = 0
    is_first = True
    while start < len(segments):
        current_size = first_size if is_first else size
        end = min(start + current_size, len(segments))
        yield start, segments[start:end]
        start = end
        is_first = False


def translation_batch_progress(end_index: int, total: int) -> float:
    safe_total = max(total, 1)
    return 0.32 + (min(end_index, safe_total) / safe_total) * 0.12


TRANSLATION_PROMPT_VERSION = 3


def translation_progress_message(*, provider_label: str, start: int, end_index: int, total: int, note: str = "") -> str:
    if start + 1 == end_index:
        return f"Đang dịch {provider_label} câu {end_index}/{total}{note}"
    return f"Đang dịch {provider_label} cụm {start + 1}-{end_index}/{total}{note}"


def joined_source_context(items: list[dict[str, Any]]) -> str:
    parts = [normalize_text(item.get("sourceText") or "") for item in items]
    return normalize_text(" ".join(part for part in parts if part))





def load_translation_cache(cache_path: Path, cache_key: str) -> dict[str, dict[str, str]]:
    if not cache_path.exists():
        return {}
    try:
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if cached.get("key") != cache_key:
        return {}
    translations = cached.get("translations", {})
    return translations if isinstance(translations, dict) else {}


def persist_translation_cache(cache_path: Path, cache_key: str, translations: dict[str, dict[str, str]]) -> None:
    cache_path.write_text(
        json.dumps({"key": cache_key, "translations": translations}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def apply_localized_result(
    item: dict[str, Any],
    localized: dict[str, Any],
    source_text: str,
) -> dict[str, str]:
    translated_text = prefer_minh_cau_pair(
        normalize_text(localized.get("translatedText") or source_text),
        item.get("sourceText") or source_text,
    )
    spoken_text = build_spoken_text(
        localized.get("spokenText") or translated_text,
        item.get("sourceText") or "",
        delivery=localized.get("delivery") or "neutral",
    )
    item["translatedText"] = translated_text
    item["spokenText"] = spoken_text or translated_text
    item["delivery"] = localized.get("delivery") or "neutral"
    return {
        "translatedText": item["translatedText"],
        "spokenText": item["spokenText"],
        "delivery": item["delivery"],
    }


def fallback_translate_items(
    batch: list[dict[str, Any]],
    *,
    texts: list[str],
    source_hint: str,
    use_llama_cpp: bool,
) -> list[dict[str, str]]:
    from .translation import localize_batch_via_llama_cpp, translate_via_google

    if use_llama_cpp:
        try:
            return localize_batch_via_llama_cpp(batch, source_hint, "vi")
        except Exception:
            pass
    localized_items: list[dict[str, str]] = []
    for text, source_item in zip(texts, batch):
        try:
            translated = translate_via_google(text, source_hint, "vi") if text else ""
        except Exception:
            translated = ""
            
        translated = prefer_minh_cau_pair(translated or text, source_item.get("sourceText") or "")
        spoken = build_spoken_text(translated or text, source_item.get("sourceText") or "")
        localized_items.append(
            {
                "translatedText": translated or text,
                "spokenText": spoken or translated or text,
                "delivery": "neutral",
            }
        )
    return localized_items


def localize_batch_via_ollama_resilient(
    batch: list[dict[str, Any]],
    *,
    source_hint: str,
    target_language: str,
    llama_cpp_available: bool,
    label: str,
    phase: str,
    progress_hint: float,
) -> list[dict[str, str]]:
    from .translation import localize_batch_via_ollama

    texts = [normalize_text(item.get("sourceText") or "") for item in batch]
    try:
        return localize_batch_via_ollama(batch, source_hint, target_language)
    except Exception as exc:
        if len(batch) == 1:
            extended_timeout = min(
                OLLAMA_MAX_TIMEOUT,
                max(estimate_ollama_timeout(texts[0], max_tokens=OLLAMA_TOKENS_MIN, attempt=2), OLLAMA_TIMEOUT + 90),
            )
            if extended_timeout > OLLAMA_TIMEOUT:
                emit_progress(
                    phase=phase,
                    step="translate",
                    progress=progress_hint,
                    message=f"Ollama chậm ở cụm {label}, thử lại riêng cụm này với timeout={extended_timeout}s",
                )
                try:
                    return localize_batch_via_ollama(
                        batch,
                        source_hint,
                        target_language,
                        timeout=extended_timeout,
                    )
                except Exception as retry_exc:
                    exc = retry_exc
        if len(batch) > 1:
            emit_progress(
                phase=phase,
                step="translate",
                progress=progress_hint,
                message=f"Ollama chậm ở cụm {label}, đang tách nhỏ để tránh đứng tiến trình",
            )
            midpoint = max(len(batch) // 2, 1)
            left = localize_batch_via_ollama_resilient(
                batch[:midpoint],
                source_hint=source_hint,
                target_language=target_language,
                llama_cpp_available=llama_cpp_available,
                label=f"{label}.1",
                phase=phase,
                progress_hint=progress_hint,
            )
            right = localize_batch_via_ollama_resilient(
                batch[midpoint:],
                source_hint=source_hint,
                target_language=target_language,
                llama_cpp_available=llama_cpp_available,
                label=f"{label}.2",
                phase=phase,
                progress_hint=progress_hint,
            )
            return left + right
        emit_progress(
            phase=phase,
            step="translate",
            progress=progress_hint,
            message=f"Ollama lỗi ở cụm {label}, đang fallback cục bộ cho cụm này",
            extra={"warning": normalize_text(str(exc))[:180]},
        )
        return fallback_translate_items(
            batch,
            texts=texts,
            source_hint=source_hint,
            use_llama_cpp=llama_cpp_available,
        )


def parse_json_response_payload(output_text: str) -> Any:
    text = str(output_text or "").strip()
    if not text:
        raise RuntimeError("LLM returned an empty payload.")
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"(\[[\s\S]*\]|\{[\s\S]*\})", text)
        if not match:
            raise
        return json.loads(match.group(1))


def discover_llama_cpp_binary() -> Path | None:
    candidates: list[Path] = []
    if LLAMA_CPP_BIN:
        candidates.append(Path(LLAMA_CPP_BIN).expanduser())
    candidates.extend(
        [
            ROOT / "tools" / "llama-cli.exe",
            ROOT / "tools" / "llama.cpp" / "llama-cli.exe",
            ROOT / "tools" / "main.exe",
            ROOT / "tools" / "llama.cpp" / "main.exe",
        ]
    )
    for executable_name in ("llama-cli.exe", "llama-cli", "main.exe", "main"):
        resolved = shutil.which(executable_name)
        if resolved:
            candidates.append(Path(resolved))
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def discover_llama_cpp_model() -> Path | None:
    candidates: list[Path] = []
    if LLAMA_CPP_MODEL:
        candidates.append(Path(LLAMA_CPP_MODEL).expanduser())
    model_name_tokens = tuple(
        token for token in {LLAMA_CPP_MODEL_NAME.lower(), LLAMA_CPP_MODEL_NAME.lower().replace("-", "")} if token
    )
    for folder in (
        ROOT / "temp" / "models",
        ROOT / "models",
        ROOT / "assets" / "models",
    ):
        if not folder.exists():
            continue
        preferred: list[Path] = []
        fallbacks: list[Path] = []
        for candidate in sorted(folder.glob("*.gguf")):
            normalized_name = candidate.name.lower().replace("-", "").replace("_", "")
            if any(token.replace("_", "") in normalized_name for token in model_name_tokens):
                preferred.append(candidate)
            else:
                fallbacks.append(candidate)
        candidates.extend(preferred)
        candidates.extend(fallbacks)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def should_use_llama_cpp(provider: str) -> bool:
    normalized = str(provider or "").strip().lower()
    binary = discover_llama_cpp_binary()
    model = discover_llama_cpp_model()
    if normalized in {"llama_cpp", "llama.cpp"}:
        if not binary or not model:
            raise RuntimeError("Da chon provider llama.cpp nhung chua tim thay `llama-cli/main` hoac model GGUF. Hay cau hinh `DUB_LLAMA_CPP_BIN` va `DUB_LLAMA_CPP_MODEL`.")
        return True
    if normalized == "auto":
        return bool(binary and model)
    return False


def run_llama_cpp_prompt(prompt: str, *, max_tokens: int, temperature: float | None = None, timeout: float | None = None) -> str:
    binary = discover_llama_cpp_binary()
    model = discover_llama_cpp_model()
    if not binary or not model:
        raise RuntimeError("Khong tim thay llama.cpp binary/model. Hay cau hinh `DUB_LLAMA_CPP_BIN` va `DUB_LLAMA_CPP_MODEL`.")
    command = [
        str(binary),
        "-m",
        str(model),
        "-c",
        str(LLAMA_CPP_CTX),
        "-n",
        str(max_tokens),
        "-t",
        str(LLAMA_CPP_THREADS),
        "--temp",
        f"{LLAMA_CPP_TEMP if temperature is None else temperature:.2f}",
        "--no-display-prompt",
        "-p",
        prompt,
    ]
    if LLAMA_CPP_N_GPU_LAYERS:
        command.extend(["-ngl", str(LLAMA_CPP_N_GPU_LAYERS)])
    effective_timeout = timeout if timeout is not None else LLAMA_CPP_TIMEOUT
    print(f"[info] Dang chay llama.cpp (timeout={effective_timeout}s)...", flush=True)
    completed = run(command, cwd=ROOT, capture_output=True, timeout=effective_timeout)
    output = (completed.stdout or "").strip()
    if not output:
        raise RuntimeError("llama.cpp khong tra ve noi dung nao.")
    return output


class _TemporaryDisableDeadLocalProxies:
    def __init__(self) -> None:
        self.proxy_keys = (
            "HTTP_PROXY",
            "HTTPS_PROXY",
            "http_proxy",
            "https_proxy",
            "ALL_PROXY",
            "all_proxy",
            "NO_PROXY",
            "no_proxy",
        )
        self.original: dict[str, str | None] = {}

    def __enter__(self):
        self.original = {key: os.environ.get(key) for key in self.proxy_keys}
        disabled = False
        for key in self.proxy_keys[:6]:
            normalized = normalize_text(self.original.get(key) or "").lower()
            if normalized.startswith("http://127.0.0.1:9") or normalized.startswith(
                "http://localhost:9"
            ):
                os.environ.pop(key, None)
                disabled = True
        if disabled:
            os.environ["NO_PROXY"] = "huggingface.co,pytorch.org,download.pytorch.org"
            os.environ["no_proxy"] = "huggingface.co,pytorch.org,download.pytorch.org"
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        for key, value in self.original.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        return False


class _TemporaryUseWorkspaceTorchHome:
    def __init__(self) -> None:
        self.original: str | None = None

    def __enter__(self):
        self.original = os.environ.get("TORCH_HOME")
        torch_home = ensure_dir(ROOT / "temp" / "models" / "torch")
        os.environ["TORCH_HOME"] = str(torch_home)
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        if self.original is None:
            os.environ.pop("TORCH_HOME", None)
        else:
            os.environ["TORCH_HOME"] = self.original
        return False


class _TemporaryUseWorkspaceHfHome:
    def __init__(self) -> None:
        self.original_hf_home: str | None = None
        self.original_disable_xet: str | None = None

    def __enter__(self):
        self.original_hf_home = os.environ.get("HF_HOME")
        self.original_disable_xet = os.environ.get("HF_HUB_DISABLE_XET")
        hf_home = ensure_dir(HUGGINGFACE_HUB_CACHE.parent.parent)
        os.environ["HF_HOME"] = str(hf_home)
        os.environ["HF_HUB_DISABLE_XET"] = "1"
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        if self.original_hf_home is None:
            os.environ.pop("HF_HOME", None)
        else:
            os.environ["HF_HOME"] = self.original_hf_home
        if self.original_disable_xet is None:
            os.environ.pop("HF_HUB_DISABLE_XET", None)
        else:
            os.environ["HF_HUB_DISABLE_XET"] = self.original_disable_xet
        return False


def temporarily_disable_dead_local_proxies():
    proxy_keys = (
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "http_proxy",
        "https_proxy",
        "ALL_PROXY",
        "all_proxy",
        "NO_PROXY",
        "no_proxy",
    )
    original: dict[str, str | None] = {}

    class _ProxyContext:
        def __enter__(self):
            nonlocal original
            original = {key: os.environ.get(key) for key in proxy_keys}
            disabled = False
            for key in proxy_keys[:6]:
                normalized = normalize_text(original.get(key) or "").lower()
                if normalized.startswith("http://127.0.0.1:9") or normalized.startswith(
                    "http://localhost:9"
                ):
                    os.environ.pop(key, None)
                    disabled = True
            if disabled:
                os.environ["NO_PROXY"] = "huggingface.co,pytorch.org,download.pytorch.org"
                os.environ["no_proxy"] = "huggingface.co,pytorch.org,download.pytorch.org"
            return self

        def __exit__(self, exc_type, exc, tb) -> bool:
            for key, value in original.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
            return False

    return _ProxyContext()


def temporarily_use_workspace_torch_home():
    original = os.environ.get("TORCH_HOME")

    class _TorchHomeContext:
        def __enter__(self):
            torch_home = ensure_dir(ROOT / "temp" / "models" / "torch")
            os.environ["TORCH_HOME"] = str(torch_home)
            return self

        def __exit__(self, exc_type, exc, tb) -> bool:
            if original is None:
                os.environ.pop("TORCH_HOME", None)
            else:
                os.environ["TORCH_HOME"] = original
            return False

    return _TorchHomeContext()


def temporarily_use_workspace_hf_home():
    original_hf_home = os.environ.get("HF_HOME")
    original_disable_xet = os.environ.get("HF_HUB_DISABLE_XET")

    class _HfHomeContext:
        def __enter__(self):
            hf_home = ensure_dir(HUGGINGFACE_HUB_CACHE.parent.parent)
            os.environ["HF_HOME"] = str(hf_home)
            os.environ["HF_HUB_DISABLE_XET"] = "1"
            return self

        def __exit__(self, exc_type, exc, tb) -> bool:
            if original_hf_home is None:
                os.environ.pop("HF_HOME", None)
            else:
                os.environ["HF_HOME"] = original_hf_home
            if original_disable_xet is None:
                os.environ.pop("HF_HUB_DISABLE_XET", None)
            else:
                os.environ["HF_HUB_DISABLE_XET"] = original_disable_xet
            return False

    return _HfHomeContext()


def resolve_hf_token() -> str:
    for key in ("HF_TOKEN", "HUGGINGFACE_TOKEN", "HUGGING_FACE_HUB_TOKEN"):
        value = os.getenv(key, "").strip()
        if value:
            return value
    return ""


def ensure_whisperx_runtime(*, phase: str, step: str, progress: float) -> None:
    ensure_python_packages(
        [
            ("whisperx", "whisperx"),
            ("torchaudio", "torchaudio"),
            ("pyannote.audio", "pyannote.audio"),
        ],
        phase=phase,
        step=step,
        progress=progress,
        message="Đang tự động cài WhisperX và các gói phụ trợ...",
    )
    ensure_whisperx_model_cache(
        phase=phase,
        step=step,
        progress=min(progress + 0.01, 0.99),
    )
    preload_languages = list(dict.fromkeys([*LANGUAGE_OPTIONS, "vi"]))
    for index, language_code in enumerate(preload_languages, start=1):
        ensure_whisperx_align_cache(
            language_code=language_code,
            phase=phase,
            step=step,
            progress=min(progress + 0.01 + index * 0.005, 0.995),
        )
    if resolve_hf_token():
        try:
            ensure_whisperx_diarization_cache(
                phase=phase,
                step=step,
                progress=min(progress + 0.04, 0.998),
            )
        except Exception as exc:
            print(
                f"[warn] WhisperX diarization cache chưa sẵn sàng, sẽ tiếp tục với ASR/alignment và fallback speaker nếu cần: {normalize_text(str(exc))[:220]}",
                flush=True,
            )


def ensure_edge_tts_runtime(*, phase: str, step: str, progress: float) -> None:
    ensure_python_packages(
        [("edge_tts", "edge-tts")],
        phase=phase,
        step=step,
        progress=progress,
        message="Đang tự động cài edge-tts...",
    )


def ensure_source_separation_runtime(*, phase: str, step: str, progress: float) -> None:
    if not DUB_SOURCE_SEPARATION_ENABLED:
        return
    if DUB_SOURCE_SEPARATION_PROVIDER.startswith("torchaudio"):
        ensure_python_packages(
            [("torchaudio", "torchaudio")],
            phase=phase,
            step=step,
            progress=progress,
            message="Đang kiểm tra runtime tách lời gốc khỏi nhạc nền...",
        )
        return
    if DUB_SOURCE_SEPARATION_PROVIDER == "demucs":
        ensure_python_packages(
            [("demucs", "demucs")],
            phase=phase,
            step=step,
            progress=progress,
            message="Đang tự động cài Demucs để tách lời gốc khỏi nhạc nền...",
        )


def ensure_vieneu_runtime(*, phase: str, step: str, progress: float) -> None:
    if importlib.util.find_spec("vieneu") is None:
        emit_progress(
            phase=phase,
            step=step,
            progress=max(progress - 0.02, 0.0),
            message="Đang cài VieNeu-TTS SDK từ repo local...",
        )
        vieneu_repo_dir = ROOT / "tools" / "vieneu_repo"
        install_cmd = [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
        ]
        if vieneu_repo_dir.exists():
            install_cmd.extend(
                [
                    "-e",
                    str(vieneu_repo_dir),
                    "--extra-index-url",
                    VIENEU_PIP_EXTRA_INDEX,
                ]
            )
        else:
            install_cmd.extend(
                [
                    "vieneu",
                    "--extra-index-url",
                    VIENEU_PIP_EXTRA_INDEX,
                ]
            )
        run(install_cmd)
        importlib.invalidate_caches()
    emit_progress(
        phase=phase,
        step=step,
        progress=progress,
        message="Đang khởi động VieNeu-TTS và đồng bộ model local...",
    )
    from tools.vieneu_wrapper import get_vieneu_provider

    get_vieneu_provider()


def prepare_runtime(target: str) -> None:
    normalized = str(target or "all").strip().lower()
    if normalized not in {"analysis", "render", "all"}:
        normalized = "all"
    if normalized in {"analysis", "all"}:
        if not whisperx_disabled():
            ensure_whisperx_runtime(phase="analysis", step="prepare", progress=0.02)
        ensure_local_whisper_model(phase="analysis", step="prepare", progress=0.03)
        if DUB_TRANSLATE_PROVIDER in {"ollama", "auto"}:
            ensure_ollama_runtime(
                required=DUB_TRANSLATE_PROVIDER == "ollama",
                phase="analysis",
                step="prepare",
                progress=0.04,
            )
    if normalized in {"render", "all"}:
        ensure_edge_tts_runtime(phase="render", step="prepare", progress=0.03)
        if DUB_SOURCE_SEPARATION_ENABLED:
            ensure_source_separation_runtime(phase="render", step="prepare", progress=0.04)
        if DUB_USE_VIENEU:
            ensure_vieneu_runtime(phase="render", step="prepare", progress=0.05)
        if DUB_TRANSLATE_PROVIDER in {"ollama", "auto"}:
            ensure_ollama_runtime(
                required=DUB_TRANSLATE_PROVIDER == "ollama",
                phase="render",
                step="prepare",
                progress=0.06,
            )


def import_whisperx_module() -> Any:
    if whisperx_disabled():
        raise RuntimeError("WhisperX/Hugging Face da duoc tat boi cau hinh local.")
    ensure_whisperx_runtime(phase="analysis", step="prepare", progress=0.02)
    import whisperx  # type: ignore
    return whisperx


def whisperx_torch_runtime() -> Any | None:
    try:
        import torch  # type: ignore
    except Exception:
        return None
    return torch


def preferred_whisperx_device() -> str:
    torch = whisperx_torch_runtime()
    if DUB_USE_GPU and torch is not None and bool(torch.cuda.is_available()):
        return "cuda"
    return "cpu"


def preferred_whisperx_compute_type(device: str) -> str:
    if device == "cuda":
        return WHISPERX_COMPUTE_TYPE
    return "int8"


def whisperx_audio_waveform(audio: Any) -> dict[str, Any]:
    torch = whisperx_torch_runtime()
    if torch is None:
        raise RuntimeError("Torch is required for WhisperX waveform conversion.")
    return {
        "waveform": torch.tensor(audio).unsqueeze(0),
        "sample_rate": 16000,
    }
