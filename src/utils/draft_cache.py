from collections import OrderedDict
import src.pyJianYingDraft as draft
from typing import Dict
DRAFT_CACHE: Dict[str, 'draft.ScriptFile'] = OrderedDict()
MAX_CACHE_SIZE = 100

def update_cache(key: str, value: draft.ScriptFile) -> None:
    """Update LRU cache"""
    if key in DRAFT_CACHE:
        DRAFT_CACHE.pop(key)
    elif len(DRAFT_CACHE) >= MAX_CACHE_SIZE:
        print(f'{key}, Cache is full, deleting the least recently used item')
        DRAFT_CACHE.popitem(last=False)
        DRAFT_CACHE[key] = value