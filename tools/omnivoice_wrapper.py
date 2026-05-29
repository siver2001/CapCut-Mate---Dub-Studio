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

        # Load OmniVoice on CPU using standard single-precision float32 for stable CPU inference
        self._model = OmniVoice.from_pretrained(
            "k2-fsa/OmniVoice", 
            device_map="cpu", 
            dtype=torch.float32
        )

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
            # Synthesize audio using OmniVoice voice cloning
            audio = self._model.generate(
                text=clean_text,
                ref_audio=str(ref_audio),
                ref_text=str(ref_text or "").strip() or None
            )
        else:
            resolved_instruct = str(voice_name or "").strip()
            if not resolved_instruct:
                resolved_instruct = "female, young adult, moderate pitch"
            
            # Synthesize audio using OmniVoice voice design
            audio = self._model.generate(
                text=clean_text,
                instruct=resolved_instruct
            )
        
        # Save output audio using soundfile at 24000 Hz sample rate
        import soundfile as sf
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
