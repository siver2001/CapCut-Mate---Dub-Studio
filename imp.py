import types
import importlib.util
import os
import sys

def find_module(name, path=None):
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

def new_module(name):
    return types.ModuleType(name)

# Make sure if someone imports this, it acts exactly like the imp module
sys.modules['imp'] = sys.modules[__name__]
