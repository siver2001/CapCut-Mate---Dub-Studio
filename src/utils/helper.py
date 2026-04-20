from urllib.parse import urlparse, parse_qs
import datetime
import uuid
from pathlib import Path

def get_url_param(url: str, key: str, default=None):
    """Extract a query parameter value from a URL."""
    try:
        query = parse_qs(urlparse(url).query)
        return query.get(key, [default])[0]
    except Exception:
        return default

def gen_unique_id() -> str:
    """Generate a unique ID string based on timestamp and UUID."""
    timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    unique_id = uuid.uuid4().hex[:8]
    return f'{timestamp}{unique_id}'

def get_all_files(directory: str) -> list:
    """Recursively get all file paths in a directory."""
    path_obj = Path(directory)
    if not path_obj.exists():
        return []
    return [str(f) for f in path_obj.rglob('*') if f.is_file()]