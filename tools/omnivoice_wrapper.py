from __future__ import annotations

import atexit
import os
import shutil
import sys
from pathlib import Path
from typing import Any

class OmnivoiceProvider:
    _instance: "OmnivoiceProvider | None" = None
    _model: Any = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, model_dir: Path | None = None):
        if self._model is not None:
            return

        import torch
        from omnivoice import OmniVoice
        from tools.dub_studio.config import DUB_OMNIVOICE_DEVICE

        # Determine device and dtype
        device = "cpu"
        dtype = torch.float32

        if DUB_OMNIVOICE_DEVICE in ("cuda", "gpu"):
            if torch.cuda.is_available():
                device = "cuda"
                dtype = torch.float16
            else:
                print("[warn] CUDA is not available in PyTorch. Falling back to CPU for OmniVoice.", file=sys.stderr)
                device = "cpu"
                dtype = torch.float32
        elif DUB_OMNIVOICE_DEVICE == "auto":
            if torch.cuda.is_available():
                device = "cuda"
                dtype = torch.float16
            else:
                device = "cpu"
                dtype = torch.float32
        else:
            device = "cpu"
            dtype = torch.float32

        print(f"[info] Loading OmniVoice on device: {device} with dtype: {dtype}", file=sys.stderr)

        from tools.dub_studio.config import OMNIVOICE_MODEL_DIR, HUGGINGFACE_HUB_CACHE

        model_path = "k2-fsa/OmniVoice"
        use_offline = False

        # 1. Check if model exists in OMNIVOICE_MODEL_DIR
        if OMNIVOICE_MODEL_DIR.exists() and (OMNIVOICE_MODEL_DIR / "model.safetensors").exists():
            model_path = str(OMNIVOICE_MODEL_DIR)
            use_offline = True
            print(f"[info] Found OmniVoice model locally in: {model_path}", file=sys.stderr)
        else:
            # 2. Check if model exists in HuggingFace cache folder
            hf_cached_dir = HUGGINGFACE_HUB_CACHE / "models--k2-fsa--OmniVoice" / "snapshots"
            if not hf_cached_dir.exists():
                alt_dir = HUGGINGFACE_HUB_CACHE.parent.parent / "hub" / "models--k2-fsa--OmniVoice" / "snapshots"
                if alt_dir.exists():
                    hf_cached_dir = alt_dir

            if hf_cached_dir.exists():
                try:
                    snapshots = [d for d in hf_cached_dir.iterdir() if d.is_dir()]
                    if snapshots:
                        snapshots.sort(key=lambda x: x.stat().st_mtime, reverse=True)
                        for snapshot in snapshots:
                            if (snapshot / "model.safetensors").exists():
                                model_path = str(snapshot)
                                use_offline = True
                                print(f"[info] Found OmniVoice model in HuggingFace cache: {model_path}", file=sys.stderr)
                                break
                except Exception as e:
                    print(f"[warn] Failed to search HuggingFace cache: {e}", file=sys.stderr)

        old_hf_offline = os.environ.get("HF_HUB_OFFLINE")
        old_tf_offline = os.environ.get("TRANSFORMERS_OFFLINE")
        if use_offline:
            os.environ["HF_HUB_OFFLINE"] = "1"
            os.environ["TRANSFORMERS_OFFLINE"] = "1"

        try:
            self._model = OmniVoice.from_pretrained(
                model_path, 
                device_map=device, 
                dtype=dtype
            )
        except (OSError, MemoryError) as mem_err:
            # Restore env vars before raising
            if use_offline:
                if old_hf_offline is None:
                    os.environ.pop("HF_HUB_OFFLINE", None)
                else:
                    os.environ["HF_HUB_OFFLINE"] = old_hf_offline
                if old_tf_offline is None:
                    os.environ.pop("TRANSFORMERS_OFFLINE", None)
                else:
                    os.environ["TRANSFORMERS_OFFLINE"] = old_tf_offline
            err_str = str(mem_err)
            if "paging file" in err_str.lower() or "1455" in err_str or isinstance(mem_err, MemoryError):
                raise RuntimeError(
                    "Không đủ bộ nhớ RAM để tải mô hình OmniVoice. "
                    "Vui lòng đóng bớt các ứng dụng khác hoặc tăng Virtual Memory (Page File) trong Windows. "
                    "Nếu máy có GPU, hãy đảm bảo đã cài PyTorch phiên bản CUDA để giảm tải bộ nhớ RAM."
                ) from mem_err
            raise
        finally:
            if use_offline:
                if old_hf_offline is None:
                    os.environ.pop("HF_HUB_OFFLINE", None)
                else:
                    os.environ["HF_HUB_OFFLINE"] = old_hf_offline
                if old_tf_offline is None:
                    os.environ.pop("TRANSFORMERS_OFFLINE", None)
                else:
                    os.environ["TRANSFORMERS_OFFLINE"] = old_tf_offline

    def list_preset_voices(self) -> list[tuple[str, str]]:
        return []

    def synthesize(
        self,
        text: str,
        output_path: Path,
        *,
        voice_name: str | None = None,
        ref_audio: Path | None = None,
        ref_text: str | None = None,
    ) -> bool:
        clean_text = str(text or "").strip()
        if not clean_text:
            raise RuntimeError("OmniVoice-TTS synthesis skipped because text is empty.")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        if ref_audio is not None and Path(ref_audio).exists():
            # Load audio using soundfile to bypass torchcodec (avoids libtorchcodec loading errors on Windows / packaged builds)
            import torch
            import soundfile as sf
            try:
                data, samplerate = sf.read(str(ref_audio))
                if data.ndim > 1:
                    data = data.mean(axis=1)
                waveform_tensor = torch.from_numpy(data).float().unsqueeze(0)
                ref_audio_param = (waveform_tensor, samplerate)
                
                # Truncate ref_text if it is too long for the audio duration to prevent OmniVoice from generating prefix text
                if ref_text:
                    duration_sec = len(data) / samplerate
                    words = str(ref_text).split()
                    max_words = max(5, int(duration_sec * 3.5))
                    if len(words) > max_words:
                        old_ref_text = ref_text
                        ref_text = " ".join(words[:max_words])
                        print(f"[info] Truncating ref_text from {len(words)} to {max_words} words (duration: {duration_sec:.2f}s) to match audio length. Old: {repr(old_ref_text)} -> New: {repr(ref_text)}", file=sys.stderr, flush=True)
            except Exception:
                ref_audio_param = str(ref_audio)

            # Synthesize audio using OmniVoice voice cloning
            print(f"[debug-omnivoice] Generating text='{clean_text}', ref_audio_param_type={type(ref_audio_param)}, ref_text='{ref_text}'", file=sys.stderr, flush=True)
            try:
                audio = self._model.generate(
                    text=clean_text,
                    ref_audio=ref_audio_param,
                    ref_text=str(ref_text or "").strip() or None
                )
                print(f"[debug-omnivoice] Generated successfully, audio type={type(audio)}, len={len(audio) if audio is not None else 'None'}", file=sys.stderr, flush=True)
                if audio is not None and len(audio) > 0:
                    print(f"[debug-omnivoice] audio[0] shape={audio[0].shape}", file=sys.stderr, flush=True)
            except Exception as e:
                print(f"[debug-omnivoice] Error during generate: {e}", file=sys.stderr, flush=True)
                raise
        else:
            resolved_instruct = str(voice_name or "").strip()
            if not resolved_instruct:
                resolved_instruct = "female, young adult, moderate pitch"
            
            # Synthesize audio using OmniVoice voice design
            print(f"[debug-omnivoice] Generating design text='{clean_text}', instruct='{resolved_instruct}'", file=sys.stderr, flush=True)
            try:
                audio = self._model.generate(
                    text=clean_text,
                    instruct=resolved_instruct
                )
                print(f"[debug-omnivoice] Generated design successfully, audio type={type(audio)}, len={len(audio) if audio is not None else 'None'}", file=sys.stderr, flush=True)
                if audio is not None and len(audio) > 0:
                    print(f"[debug-omnivoice] audio[0] shape={audio[0].shape}", file=sys.stderr, flush=True)
            except Exception as e:
                print(f"[debug-omnivoice] Error during generate: {e}", file=sys.stderr, flush=True)
                raise
        
        # Save output audio using soundfile at 24000 Hz sample rate
        import soundfile as sf
        if audio is None or len(audio) == 0 or audio[0] is None or len(audio[0]) == 0:
            raise RuntimeError("OmniVoice-TTS returned empty or null audio waveform.")
        sf.write(str(output_path), audio[0], 24000)
        
        return output_path.exists() and output_path.stat().st_size > 0

    def close(self) -> None:
        self._model = None


def get_omnivoice_provider() -> OmnivoiceProvider:
    return OmnivoiceProvider()


def close_omnivoice_provider() -> None:
    provider = OmnivoiceProvider._instance
    if provider is not None:
        provider.close()


atexit.register(close_omnivoice_provider)
