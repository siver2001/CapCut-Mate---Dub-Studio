import sys
import os

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

# Legacy shim for 'imp' module (removed in Python 3.12+)
# Needed for 'vinorm' and other legacy dependencies
try:
    import imp
except ImportError:
    import types
    import importlib.util
    
    _imp_shim = types.ModuleType('imp')
    def _find_module(name, path=None):
        import sys, os
        import importlib.util
        if getattr(sys, 'frozen', False):
            meipass = getattr(sys, '_MEIPASS', os.path.abspath(os.path.dirname(sys.executable)))
            pkg_path = os.path.join(meipass, name)
            if os.path.isdir(pkg_path):
                return (None, pkg_path, (None, None, None))
                
        spec = importlib.util.find_spec(name, path)
        if spec is None: raise ImportError(f"No module named {name}")
        origin = getattr(spec, "origin", None)
        if origin and origin.endswith('__init__.py'):
            origin = os.path.dirname(origin)
        elif getattr(spec, "submodule_search_locations", None):
            origin = spec.submodule_search_locations[0]
        else:
            if getattr(sys, 'frozen', False):
                origin = os.path.join(getattr(sys, '_MEIPASS', ''), name)
            else:
                origin = name
        return (None, origin, (None, None, None))
    
    _imp_shim.find_module = _find_module
    _imp_shim.new_module = lambda name: types.ModuleType(name)
    sys.modules['imp'] = _imp_shim

# ---------------------------------------------------------
# PyInstaller Worker / Pipeline Entry Mode
# ---------------------------------------------------------
if len(sys.argv) > 1:
    mode = sys.argv[1]
    if mode == "pipeline":
        # If called with 'pipeline' argument, act as the dub studio worker.
        sys.argv.pop(1)
        # Add root to path for imports
        root = os.path.dirname(os.path.abspath(__file__))
        if root not in sys.path:
            sys.path.insert(0, root)
        from tools.dub_studio_pipeline import main as run_pipeline
        sys.exit(run_pipeline())
    elif mode == "yt_dlp":
        # Act as yt-dlp entry point
        sys.argv.pop(1)
        import yt_dlp
        sys.exit(yt_dlp.main())
    elif mode == "-m" and len(sys.argv) > 2:
        module_name = sys.argv[2]
        sys.argv.pop(1) # remove -m
        sys.argv.pop(1) # remove module_name
        
        # Add root to path for imports
        root = os.path.dirname(os.path.abspath(__file__))
        if root not in sys.path:
            sys.path.insert(0, root)
            
        import importlib
        try:
            # Try running the __main__ of the module
            mod = importlib.import_module(f"{module_name}.__main__")
            if hasattr(mod, "main"):
                try:
                    sys.exit(mod.main())
                except Exception as e:
                    print(f"Error executing {module_name}.main(): {e}")
                    sys.exit(1)
            else:
                print(f"No main function found in {module_name}.__main__")
                sys.exit(1)
        except ImportError:
            try:
                mod = importlib.import_module(module_name)
                if hasattr(mod, "main"):
                    try:
                        sys.exit(mod.main())
                    except Exception as e:
                        print(f"Error executing {module_name}.main(): {e}")
                        sys.exit(1)
                else:
                    print(f"No main function found in {module_name}")
                    sys.exit(1)
            except Exception as e:
                print(f"Failed to execute module {module_name}: {e}")
                sys.exit(1)
    elif mode == "douyin":
        # Act as douyin downloader entry point
        sys.argv.pop(1)
        root = os.path.dirname(os.path.abspath(__file__))
        if root not in sys.path:
            sys.path.insert(0, root)
        from tools.douyin_api_downloader import main as run_douyin
        sys.exit(run_douyin())


from gui.main import main
if __name__ == "__main__":
    sys.exit(main())