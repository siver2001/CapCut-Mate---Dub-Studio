import os
import sys
import shutil
import tempfile
import importlib
import wave
from pathlib import Path
from typing import List, Optional

# Constants
VALTEC_REPO_SRC = Path(__file__).parent / "valtec_repo"

# Singleton instance
_provider = None

def get_valtec_provider(preload_zeroshot=False):
    global _provider
    if _provider is None:
        _provider = ValtecProvider()
    return _provider

def _preload_external_tts_deps() -> None:
    """
    Preload common heavy libraries to avoid deadlocks during dynamic path modification.
    pyarrow/pandas may scan sys.path during import and can fail on Windows when they 
    encounter the vendored Valtec repository directory.
    """
    for module_name in ("pyarrow", "pandas"):
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
    # Clear stale modules from the repo if they exist
    loaded_src = sys.modules.get("src")
    if loaded_src is not None:
        loaded_src_file = str(getattr(loaded_src, "__file__", "") or "")
        if repo_path not in loaded_src_file:
            for module_name in list(sys.modules):
                if module_name == "src" or module_name.startswith("src."):
                    sys.modules.pop(module_name, None)

def _deactivate_valtec_repo_path() -> None:
    repo_path = str(VALTEC_REPO_SRC)
    sys.path[:] = [path for path in sys.path if path != repo_path]

class ValtecProvider:
    def __init__(self):
        root = Path(__file__).parent.parent
        self.model_dir = root / "temp" / "models" / "valtec"
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self._tts = None
        self._zero_shot = None
        
        # Load GPU settings from config if possible
        try:
            from tools.dub_studio.config import DUB_USE_GPU, DUB_GPU_DEVICE
            use_gpu = DUB_USE_GPU
            gpu_idx = DUB_GPU_DEVICE
        except ImportError:
            use_gpu = os.environ.get("DUB_USE_GPU") == "True"
            gpu_idx = os.environ.get("DUB_GPU_DEVICE", "0")
            
        self.device = f"cuda:{gpu_idx}" if use_gpu else "cpu"
        
        # Setup runtime temp dir
        temp_root = self.model_dir / "runtime_tmp"
        temp_root.mkdir(parents=True, exist_ok=True)
        self.temp_dir = Path(tempfile.mkdtemp(dir=str(temp_root), prefix="valtec_"))
        
    def _patch_valtec_cache_dir(self):
        cache_dir = self.temp_dir
        try:
            import valtec_tts as valtec_tts_module
            valtec_tts_module.get_cache_dir = lambda: cache_dir
        except Exception:
            pass
        try:
            import valtec_tts.zeroshot as valtec_zeroshot_module
            valtec_zeroshot_module._get_cache_dir = lambda: cache_dir
        except Exception:
            pass

    def _load_tts(self):
        if self._tts is None:
            _activate_valtec_repo_path()
            try:
                self._patch_valtec_cache_dir()
                from valtec_tts import TTS
                local_model_dir = self.model_dir / "models" / "vits-vietnamese"
                if not (local_model_dir / "config.json").exists():
                     raise RuntimeError(f"Valtec-TTS local model missing in {local_model_dir}")
                self._tts = TTS(model_path=str(local_model_dir), device=self.device)
            finally:
                _deactivate_valtec_repo_path()
        return self._tts

    def _load_zero_shot(self):
        if self._zero_shot is None:
            _activate_valtec_repo_path()
            try:
                self._patch_valtec_cache_dir()
                from valtec_tts.zeroshot import ZeroShotTTS
                model_base = self.model_dir / "models" / "zeroshot-vietnamese"
                checkpoint = model_base / "G_175000.pth"
                config = model_base / "config.json"
                self._zero_shot = ZeroShotTTS(
                    checkpoint_path=str(checkpoint),
                    config_path=str(config),
                    device=self.device
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
        # Standard speaker mapping
        VALTEC_PRESET_SPEAKER_IDS = {
            "valtec:nf": "NF", "valtec:sf": "SF", "valtec:nm1": "NM1",
            "valtec:sm": "SM", "valtec:nm2": "NM2"
        }
        
        selected_voice = voice_name or "valtec:nf"
        speaker_id = VALTEC_PRESET_SPEAKER_IDS.get(selected_voice, "NF")
        
        # Zero-shot cloning branch - ONLY if not a native preset or if prompt_audio is NOT a reference file
        is_native_preset = selected_voice in VALTEC_PRESET_SPEAKER_IDS
        
        if prompt_audio and prompt_audio.exists() and not is_native_preset:
            engine = self._load_zero_shot()
            engine.clone_voice(
                text=text,
                reference_audio=str(prompt_audio),
                output_path=str(output_path),
                length_scale=speed
            )
        else:
            # Native preset branch
            engine = self._load_tts()
            engine.speak(
                text=text,
                speaker=speaker_id,
                output_path=str(output_path),
                speed=speed
            )
            
        return output_path.exists() and output_path.stat().st_size > 0

    def close(self):
        if self._tts:
            self._tts = None
        if self._zero_shot:
            self._zero_shot = None
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)
