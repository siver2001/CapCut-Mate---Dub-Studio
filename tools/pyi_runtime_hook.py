import sys
import os

if getattr(sys, 'frozen', False):
    application_path = sys._MEIPASS
    
    # Ensure extraction directory is in path
    if application_path not in sys.path:
        sys.path.insert(0, application_path)
    
    # Add _internal directory to path for onedir mode
    internal_dir = os.path.join(application_path, '_internal')
    if os.path.exists(internal_dir) and internal_dir not in sys.path:
        sys.path.insert(0, internal_dir)
        
    # Vendor packages (viphoneme, vinorm, etc.) need explicit paths when frozen
    os.environ['VI_PHONEME_PATH'] = os.path.join(internal_dir if os.path.exists(internal_dir) else application_path, 'viphoneme')
    os.environ['VINORM_PATH'] = os.path.join(internal_dir if os.path.exists(internal_dir) else application_path, 'vinorm')
    
    # Add tools/valtec_repo/src to path dynamically
    valtec_repo_src = os.path.join(application_path, 'tools', 'valtec_repo')
    if os.path.exists(valtec_repo_src) and valtec_repo_src not in sys.path:
        sys.path.insert(0, valtec_repo_src)

    # Mock vinorm globally to avoid loading/executing its Linux binary on Windows
    try:
        import types
        import re
        import importlib.machinery

        vinorm_mock = types.ModuleType('vinorm')
        vinorm_mock.__spec__ = importlib.machinery.ModuleSpec('vinorm', None)
        
        def TTSnorm(text, punc=False, unknown=True, lower=True, rule=False):
            normalized = str(text or "").strip()
            normalized = re.sub(r"\s+", " ", normalized)
            if lower:
                normalized = normalized.lower()
            return normalized

        vinorm_mock.TTSnorm = TTSnorm
        sys.modules['vinorm'] = vinorm_mock
    except Exception as e:
        print(f"[WARN] Failed to install vinorm mock hook: {e}", file=sys.stderr)

    # Legacy compatibility shim for 'imp' module (removed in Python 3.12+)
    # Required by 'viphoneme' to locate its text dictionaries in the PyInstaller environment
    if 'imp' not in sys.modules:
        try:
            import imp
        except ImportError:
            import importlib.util
            import importlib.machinery
            
            _imp_shim = types.ModuleType('imp')
            
            def _find_module(name, path=None):
                try:
                    spec = importlib.util.find_spec(name, path)
                    if spec is None:
                        raise ImportError(f"No module named {name}")
                    
                    origin = getattr(spec, "origin", None)
                    if origin and (origin.endswith('__init__.py') or os.path.isdir(origin)):
                        if origin.endswith('__init__.py'):
                            origin = os.path.dirname(origin)
                        return (None, origin, (None, None, 1))
                    return (None, origin, (None, None, 1))
                except Exception:
                    raise ImportError(f"No module named {name}")
            
            _imp_shim.find_module = _find_module
            _imp_shim.new_module = lambda name: types.ModuleType(name)
            _imp_shim.get_suffixes = lambda: [('.py', 'U', 1)]
            sys.modules['imp'] = _imp_shim

    # Robust workaround for PyInstaller metadata StopIteration / PackageNotFoundError crashes
    try:
        import importlib.metadata
        _original_distribution = importlib.metadata.distribution
        
        def _mock_version(package_name):
            try:
                return _original_distribution(package_name).version
            except Exception:
                fallbacks = {
                    "transformers": "5.9.0",
                    "torch": "2.12.0",
                    "torchaudio": "2.11.0",
                    "tqdm": "4.67.0",
                    "regex": "2026.0.0",
                    "requests": "2.32.0",
                    "numpy": "2.0.0",
                    "tokenizers": "0.20.0",
                    "huggingface-hub": "0.26.0",
                    "safetensors": "0.4.0",
                    "omnivoice": "0.1.5",
                }
                return fallbacks.get(package_name.lower(), "1.0.0")
                
        def _mock_metadata(package_name):
            try:
                return _original_distribution(package_name).metadata
            except Exception:
                from email.message import Message
                msg = Message()
                msg.add_header("Version", _mock_version(package_name))
                msg.add_header("Name", package_name)
                return msg

        def _mock_distribution(package_name):
            try:
                return _original_distribution(package_name)
            except Exception:
                class MockDistribution:
                    def __init__(self, name):
                        self.name = name
                    @property
                    def version(self):
                        return _mock_version(self.name)
                    @property
                    def metadata(self):
                        return _mock_metadata(self.name)
                    def read_text(self, filename):
                        return None
                return MockDistribution(package_name)

        importlib.metadata.version = _mock_version
        importlib.metadata.metadata = _mock_metadata
        importlib.metadata.distribution = _mock_distribution
    except Exception:
        pass

