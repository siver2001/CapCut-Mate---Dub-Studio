from __future__ import annotations

import atexit
import importlib.util
import os
import re
import shutil
import sys
import tempfile
import types
import wave
from pathlib import Path
from typing import Any


TOOLS_ROOT = Path(__file__).resolve().parent
VALTEC_REPO_SRC = TOOLS_ROOT / "valtec_repo"
_EXTERNAL_TTS_DEPS_PRELOADED = False


def _preload_external_tts_deps() -> None:
    global _EXTERNAL_TTS_DEPS_PRELOADED
    if _EXTERNAL_TTS_DEPS_PRELOADED:
        return
    _EXTERNAL_TTS_DEPS_PRELOADED = True
    # Load these while valtec_repo is not on sys.path. pyarrow/pandas may scan
    # sys.path during import and can fail on Windows when they encounter the
    # vendored Valtec repository directory.
    for module_name in ("pyarrow", "pandas", "sklearn", "underthesea"):
        try:
            importlib.import_module(module_name)
        except Exception:
            pass


def _activate_valtec_repo_path() -> None:
    if not VALTEC_REPO_SRC.exists():
        return
    _preload_external_tts_deps()
    repo_path = str(VALTEC_REPO_SRC)
    sys.path[:] = [path for path in sys.path if path != repo_path]
    sys.path.insert(0, repo_path)
    loaded_src = sys.modules.get("src")
    loaded_src_file = str(getattr(loaded_src, "__file__", "") or "")
    if loaded_src is not None and repo_path not in loaded_src_file:
        for module_name in list(sys.modules):
            if module_name == "src" or module_name.startswith("src."):
                sys.modules.pop(module_name, None)


def _deactivate_valtec_repo_path() -> None:
    repo_path = str(VALTEC_REPO_SRC)
    sys.path[:] = [path for path in sys.path if path != repo_path]


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
        if hasattr(self, "_initialized") and self._initialized:
            return
        self._initialized = True

        os.environ.setdefault("HF_HUB_DISABLE_SYMLINLINKS_WARNING", "1")
        from tools.dub_studio.config import VALTEC_MODEL_DIR

        self.model_dir = Path(VALTEC_MODEL_DIR)
        self.model_dir.mkdir(parents=True, exist_ok=True)
        
        # Use the system temp dir directly to avoid nesting if tempfile.tempdir was already overridden
        try:
            # On Windows, this is usually what we want before it's poisoned
            system_temp = os.environ.get("TEMP") or os.environ.get("TMP") or tempfile.gettempdir()
            # If the current temp is already inside our valtec root, go up or use a cleaner path
            if "capcut_auto_edit_valtec" in system_temp:
                 p = Path(system_temp)
                 while len(p.parts) > 1 and "capcut_auto_edit_valtec" in p.parts:
                     p = p.parent
                 system_temp = str(p)
        except Exception:
            system_temp = tempfile.gettempdir()

        temp_root = Path(
            os.environ.get("CAPCUT_VALTEC_TEMP_ROOT")
            or (self.model_dir / "runtime_tmp")
        )
        temp_root.mkdir(parents=True, exist_ok=True)
        self.temp_dir = Path(tempfile.mkdtemp(prefix="valtec_", dir=str(temp_root)))
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        atexit.register(lambda path=self.temp_dir: shutil.rmtree(path, ignore_errors=True))
        os.environ["LOCALAPPDATA"] = str(self.model_dir.parent)
        os.environ["XDG_CACHE_HOME"] = str(self.model_dir.parent)
        os.environ["TEMP"] = str(self.temp_dir)
        os.environ["TMP"] = str(self.temp_dir)
        os.environ["TMPDIR"] = str(self.temp_dir)
        os.environ["VIPHONEME_TEMP_ROOT"] = str(self.temp_dir)
        os.environ.setdefault("VIPHONEME_ISOLATE_VINORM", "0")
        tempfile.tempdir = str(self.temp_dir)
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
        _activate_valtec_repo_path()
        try:
            from valtec_tts import ZeroShotTTS
            self._load_tts()
            if include_zeroshot and ZeroShotTTS is not None:
                self._load_zero_shot()
        finally:
            _deactivate_valtec_repo_path()

    def _load_tts(self) -> Any:
        if self._tts is None:
            _activate_valtec_repo_path()
            try:
                self._patch_valtec_cache_dir()
                from valtec_tts import TTS

                local_model_dir = self.model_dir / "models" / "vits-vietnamese"
                if not (local_model_dir / "config.json").exists() or not list(local_model_dir.glob("G*.pth")):
                    raise RuntimeError(
                        f"Valtec-TTS local model is missing in {local_model_dir}. "
                        "Please run Prepare/Download models first."
                    )
                self._tts = TTS(model_path=str(local_model_dir))
            finally:
                _deactivate_valtec_repo_path()
        return self._tts

    def _load_zero_shot(self) -> Any:
        if self._zero_shot is None:
            _activate_valtec_repo_path()
            try:
                self._patch_valtec_cache_dir()
                from valtec_tts import ZeroShotTTS
                if ZeroShotTTS is None:
                    raise RuntimeError(
                        "Tinh nang Zero-shot (giong Thanh Tam, Thu Ha...) hien khong kha dung do thieu file zeroshot.py. "
                        "Vui long chon cac giong preset nhu valtec:nf, valtec:sf hoac kiem tra lai cai dat."
                    )
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
            finally:
                _deactivate_valtec_repo_path()
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
            VALTEC_PRESET_SPEAKER_IDS,
            VALTEC_REFERENCE_VOICES,
        )

        clean_text = str(text or "").strip()
        if clean_text and not clean_text[-1] in (".", "!", "?", ",", ";", ":"):
            clean_text += "."
            
        if not clean_text:
            raise RuntimeError("Valtec-TTS synthesis skipped because text is empty.")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        selected_voice = str(voice_name or "").strip()

        if selected_voice in VALTEC_REFERENCE_VOICES:
            if prompt_audio is None or not Path(prompt_audio).exists():
                if selected_voice in VALTEC_REFERENCE_VOICES:
                    expected = VALTEC_REFERENCE_VOICES[selected_voice].get("filename", "")
                    raise RuntimeError(
                        "Valtec reference voice requires its original sample file "
                        f"({expected}). Run Prepare/Download models again."
                    )
                raise RuntimeError("Valtec-TTS zero-shot requires a valid reference audio sample.")
            
            chunks = []
            sentences = re.split(r'(?<=[.!?])\s+', clean_text)
            for s in sentences:
                s = s.strip()
                if not s:
                    continue
                if len(s) <= 100:
                    chunks.append(s)
                else:
                    sub_parts = re.split(r'(?<=[,;])\s+', s)
                    curr = ""
                    for p in sub_parts:
                        if len(curr) + len(p) <= 100:
                            curr += " " + p if curr else p
                        else:
                            if curr.strip():
                                chunks.append(curr.strip())
                            curr = p
                    if curr.strip():
                        chunks.append(curr.strip())
            
            if len(chunks) <= 1:
                self._load_zero_shot().clone_voice(
                    text=clean_text + " ",
                    reference_audio=str(prompt_audio),
                    output_path=str(output_path),
                    length_scale=speed,
                )
            else:
                temp_wavs = []
                engine = self._load_zero_shot()
                for i, chunk in enumerate(chunks):
                    t_wav = Path(tempfile.gettempdir()) / f"chunk_{i}_{os.path.basename(str(output_path))}"
                    engine.clone_voice(
                        text=chunk + " ",
                        reference_audio=str(prompt_audio),
                        output_path=str(t_wav),
                        length_scale=speed,
                    )
                    if t_wav.exists() and t_wav.stat().st_size > 0:
                        temp_wavs.append(str(t_wav))
                
                if temp_wavs:
                    data = []
                    params = None
                    for f in temp_wavs:
                        with wave.open(f, 'rb') as w:
                            if params is None:
                                params = w.getparams()
                            data.append(w.readframes(w.getnframes()))
                    
                    if params:
                        with wave.open(str(output_path), 'wb') as w:
                            w.setparams(params)
                            for d in data:
                                w.writeframes(d)
                    
                    for f in temp_wavs:
                        try:
                            os.remove(f)
                        except:
                            pass
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
