from __future__ import annotations

import atexit
import os
import shutil
import sys
from pathlib import Path
from typing import Any


TOOLS_ROOT = Path(__file__).resolve().parent
VIENEU_REPO_SRC = TOOLS_ROOT / "vieneu_repo" / "src"
if VIENEU_REPO_SRC.exists() and str(VIENEU_REPO_SRC) not in sys.path:
    sys.path.insert(0, str(VIENEU_REPO_SRC))

if getattr(sys, 'frozen', False):
    import os
    meipass = getattr(sys, '_MEIPASS', os.path.abspath(os.path.dirname(sys.executable)))
    capi_dir = os.path.join(meipass, "onnxruntime", "capi")
    os.environ["PATH"] = meipass + os.pathsep + capi_dir + os.pathsep + os.environ.get("PATH", "")
    if hasattr(os, "add_dll_directory"):
        try:
            os.add_dll_directory(meipass)
        except Exception:
            pass
        try:
            os.add_dll_directory(capi_dir)
        except Exception:
            pass


class VieneuProvider:
    _instance: "VieneuProvider | None" = None
    _model: Any = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, model_dir: Path | None = None):
        if self._model is not None:
            return

        from tools.dub_studio.config import (
            VIENEU_BACKBONE_FILENAME,
            VIENEU_BACKBONE_REPO,
            VIENEU_CODEC_REPO,
            VIENEU_DECODER_FILENAME,
            VIENEU_ENCODER_FILENAME,
            VIENEU_MODEL_DIR,
            VIENEU_REQUIRED_FILES,
        )

        os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
        self.model_dir = Path(model_dir or VIENEU_MODEL_DIR)
        self.model_dir.mkdir(parents=True, exist_ok=True)

        if not all((self.model_dir / filename).exists() for filename in VIENEU_REQUIRED_FILES):
            self._sync_local_assets(
                backbone_repo=VIENEU_BACKBONE_REPO,
                codec_repo=VIENEU_CODEC_REPO,
                backbone_filename=VIENEU_BACKBONE_FILENAME,
                decoder_filename=VIENEU_DECODER_FILENAME,
                encoder_filename=VIENEU_ENCODER_FILENAME,
            )

        from vieneu import Vieneu

        self._model = Vieneu(
            backbone_repo=str(self.model_dir / VIENEU_BACKBONE_FILENAME),
            decoder_repo=str(self.model_dir / VIENEU_DECODER_FILENAME),
            encoder_repo=str(self.model_dir / VIENEU_ENCODER_FILENAME),
        )

    def _sync_local_assets(
        self,
        *,
        backbone_repo: str,
        codec_repo: str,
        backbone_filename: str,
        decoder_filename: str,
        encoder_filename: str,
    ) -> None:
        from huggingface_hub import hf_hub_download

        download_specs = [
            (backbone_repo, backbone_filename, self.model_dir / backbone_filename),
            (backbone_repo, "voices.json", self.model_dir / "voices.json"),
            (codec_repo, decoder_filename, self.model_dir / decoder_filename),
            (codec_repo, encoder_filename, self.model_dir / encoder_filename),
        ]

        for repo_id, filename, output_path in download_specs:
            if output_path.exists():
                continue
            source_path = self._resolve_asset_path(repo_id=repo_id, filename=filename, downloader=hf_hub_download)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, output_path)

    @staticmethod
    def _resolve_asset_path(*, repo_id: str, filename: str, downloader) -> Path:
        try:
            return Path(
                downloader(
                    repo_id=repo_id,
                    filename=filename,
                    local_files_only=True,
                )
            )
        except Exception:
            return Path(
                downloader(
                    repo_id=repo_id,
                    filename=filename,
                )
            )

    def list_preset_voices(self) -> list[tuple[str, str]]:
        return list(self._model.list_preset_voices())

    def synthesize(
        self,
        text: str,
        output_path: Path,
        *,
        voice_name: str | None = None,
    ) -> bool:
        from tools.dub_studio.config import VIENEU_PRESET_VOICE_IDS

        clean_text = str(text or "").strip()
        if not clean_text:
            raise RuntimeError("VieNeu-TTS synthesis skipped because text is empty.")

        resolved_voice = VIENEU_PRESET_VOICE_IDS.get(str(voice_name or "").strip(), "")
        voice = self._model.get_preset_voice(resolved_voice or None)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        audio = self._model.infer(
            text=clean_text,
            voice=voice,
            apply_watermark=False,
            show_progress=False,
        )
        self._model.save(audio, str(output_path))
        return output_path.exists() and output_path.stat().st_size > 0

    def close(self) -> None:
        if self._model is None:
            return
        try:
            close_fn = getattr(self._model, "close", None)
            if callable(close_fn):
                close_fn()
        finally:
            self._model = None


def get_vieneu_provider() -> VieneuProvider:
    return VieneuProvider()


def close_vieneu_provider() -> None:
    provider = VieneuProvider._instance
    if provider is not None:
        provider.close()


atexit.register(close_vieneu_provider)
