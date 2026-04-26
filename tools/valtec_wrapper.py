from __future__ import annotations

import atexit
import importlib.util
import os
import sys
import types
from pathlib import Path
from typing import Any


TOOLS_ROOT = Path(__file__).resolve().parent
VALTEC_REPO_SRC = TOOLS_ROOT / "valtec_repo"


def _activate_valtec_repo_path() -> None:
    if not VALTEC_REPO_SRC.exists():
        return
    repo_path = str(VALTEC_REPO_SRC)
    sys.path[:] = [path for path in sys.path if path != repo_path]
    sys.path.insert(0, repo_path)
    loaded_src = sys.modules.get("src")
    loaded_src_file = str(getattr(loaded_src, "__file__", "") or "")
    if loaded_src is not None and repo_path not in loaded_src_file:
        for module_name in list(sys.modules):
            if module_name == "src" or module_name.startswith("src."):
                sys.modules.pop(module_name, None)


_activate_valtec_repo_path()


def _install_imp_compat_shim() -> None:
    if "imp" in sys.modules:
        return
    imp_module = types.ModuleType("imp")

    def find_module(name: str, path: list[str] | None = None):
        spec = importlib.util.find_spec(name, path)
        if spec is None:
            raise ImportError(f"No module named {name!r}")
        if spec.submodule_search_locations:
            return None, str(Path(list(spec.submodule_search_locations)[0])), ("", "", 5)
        if spec.origin:
            return None, str(Path(spec.origin).parent), ("", "", 1)
        raise ImportError(f"No module named {name!r}")

    imp_module.find_module = find_module  # type: ignore[attr-defined]
    sys.modules["imp"] = imp_module


_install_imp_compat_shim()


def _patch_vinorm_for_windows() -> None:
    try:
        import vinorm
    except ImportError:
        vinorm = types.ModuleType("vinorm")
        sys.modules["vinorm"] = vinorm

    def dummy_TTSnorm(text, **kwargs):
        try:
            from sea_g2p import Normalizer

            return Normalizer().normalize(text)
        except Exception:
            return text

    vinorm.TTSnorm = dummy_TTSnorm
    vinorm.__dict__["TTSnorm"] = dummy_TTSnorm


_patch_vinorm_for_windows()


class ValtecProvider:
    _instance: "ValtecProvider | None" = None
    _tts: Any = None
    _zero_shot: Any = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
        from tools.dub_studio.config import VALTEC_MODEL_DIR

        self.model_dir = Path(VALTEC_MODEL_DIR)
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir = self.model_dir / "tmp"
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        os.environ["LOCALAPPDATA"] = str(self.model_dir.parent)
        os.environ["XDG_CACHE_HOME"] = str(self.model_dir.parent)
        os.environ["TEMP"] = str(self.temp_dir)
        os.environ["TMP"] = str(self.temp_dir)
        os.environ["TMPDIR"] = str(self.temp_dir)
        os.environ["VIPHONEME_LOCK_PATH"] = str(self.temp_dir / "viphoneme.lock")

    def _patch_valtec_cache_dir(self) -> None:
        cache_dir = self.model_dir / "models"
        cache_dir.mkdir(parents=True, exist_ok=True)
        try:
            import valtec_tts.tts as valtec_tts_module

            valtec_tts_module.get_cache_dir = lambda: cache_dir
        except Exception:
            pass
        try:
            import valtec_tts.zeroshot as valtec_zeroshot_module

            valtec_zeroshot_module._get_cache_dir = lambda: cache_dir
        except Exception:
            pass

    def preload(self, *, include_zeroshot: bool = False) -> None:
        self._load_tts()
        if include_zeroshot:
            self._load_zero_shot()

    def _load_tts(self) -> Any:
        if self._tts is None:
            _activate_valtec_repo_path()
            self._patch_valtec_cache_dir()
            from valtec_tts import TTS

            local_model_dir = self.model_dir / "models" / "vits-vietnamese"
            if not (local_model_dir / "config.json").exists() or not list(local_model_dir.glob("G*.pth")):
                raise RuntimeError(
                    f"Valtec-TTS local model is missing in {local_model_dir}. "
                    "Please run Prepare/Download models first."
                )
            self._tts = TTS(model_path=str(local_model_dir))
        return self._tts

    def _load_zero_shot(self) -> Any:
        if self._zero_shot is None:
            _activate_valtec_repo_path()
            self._patch_valtec_cache_dir()
            from valtec_tts import ZeroShotTTS
            from tools.dub_studio.config import VALTEC_HASP_MODEL_DIR, VALTEC_ZEROSHOT_MODEL_DIR

            config_path = Path(VALTEC_ZEROSHOT_MODEL_DIR) / "config.json"
            checkpoints = sorted(Path(VALTEC_ZEROSHOT_MODEL_DIR).glob("G_*.pth"))
            hasp_path = Path(VALTEC_HASP_MODEL_DIR) / "pytorch_model.bin"
            if not config_path.exists() or not checkpoints or not hasp_path.exists():
                raise RuntimeError(
                    "Valtec zero-shot assets are missing. "
                    "Please run Prepare/Download models first."
                )
            os.environ["VALTEC_HASP_MODEL_DIR"] = str(Path(VALTEC_HASP_MODEL_DIR))

            self._zero_shot = ZeroShotTTS(
                checkpoint_path=str(checkpoints[-1]),
                config_path=str(config_path),
            )
        return self._zero_shot

    def synthesize(
        self,
        text: str,
        output_path: Path,
        *,
        voice_name: str | None = None,
        prompt_audio: Path | None = None,
        speed: float = 1.0,
    ) -> bool:
        from tools.dub_studio.config import (
            VALTEC_CLONE_PRESET,
            VALTEC_PRESET_SPEAKER_IDS,
            VALTEC_REFERENCE_VOICES,
        )

        clean_text = str(text or "").strip()
        if not clean_text:
            raise RuntimeError("Valtec-TTS synthesis skipped because text is empty.")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        selected_voice = str(voice_name or "").strip()

        if selected_voice == VALTEC_CLONE_PRESET or selected_voice in VALTEC_REFERENCE_VOICES:
            if prompt_audio is None or not Path(prompt_audio).exists():
                if selected_voice in VALTEC_REFERENCE_VOICES:
                    expected = VALTEC_REFERENCE_VOICES[selected_voice].get("filename", "")
                    raise RuntimeError(
                        "Valtec reference voice requires its original sample file "
                        f"({expected}). Run Prepare/Download models again."
                    )
                raise RuntimeError("Valtec-TTS zero-shot requires a valid reference audio sample.")
            self._load_zero_shot().clone_voice(
                text=clean_text,
                reference_audio=str(prompt_audio),
                output_path=str(output_path),
                length_scale=speed,
            )
        else:
            speaker = VALTEC_PRESET_SPEAKER_IDS.get(selected_voice, selected_voice or "NF")
            self._load_tts().speak(clean_text, speaker=speaker, output_path=str(output_path), speed=speed)

        return output_path.exists() and output_path.stat().st_size > 0

    def close(self) -> None:
        for model in (self._tts, self._zero_shot):
            close_fn = getattr(model, "close", None)
            if callable(close_fn):
                close_fn()
        self._tts = None
        self._zero_shot = None


def get_valtec_provider(*, preload_zeroshot: bool = False) -> ValtecProvider:
    provider = ValtecProvider()
    provider.preload(include_zeroshot=preload_zeroshot)
    return provider


def close_valtec_provider() -> None:
    provider = ValtecProvider._instance
    if provider is not None:
        provider.close()


atexit.register(close_valtec_provider)
