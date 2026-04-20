"""
Draft downloader utility.
Downloads draft files from API and saves them to local storage.
"""
import os
import re
import json
import time
import requests
import subprocess
from urllib.parse import urlparse, parse_qs
from typing import Optional, List, Dict
from src.utils.logger import logger
import config

def download_draft(draft_url: str, save_path: Optional[str] = None) -> bool:
    """Download a complete draft including all its assets and metadata."""
    draft_id = extract_draft_id_from_url(draft_url)
    if not draft_id:
        logger.error(f"Could not extract draft_id from URL: {draft_url}")
        return False

    target_dir = os.path.join(save_path or config.DRAFT_SAVE_PATH, draft_id)
    os.makedirs(target_dir, exist_ok=True)
    logger.info(f"Downloading draft {draft_id} to {target_dir}")

    files = get_draft_files_list(draft_url)
    if not files:
        return False

    success_count = 0
    for file_url in files:
        if download_single_file(file_url, target_dir):
            success_count += 1
    
    # Trigger directory scan to notify system of new files
    trigger_directory_scan(target_dir)
    
    logger.info(f"Draft {draft_id} download complete: {success_count}/{len(files)} files successful")
    return success_count == len(files)

def extract_draft_id_from_url(url: str) -> Optional[str]:
    try:
        query = parse_qs(urlparse(url).query)
        return query.get('draft_id', [None])[0]
    except Exception:
        return None

def get_draft_files_list(draft_url: str) -> List[str]:
    try:
        resp = requests.get(draft_url, timeout=30)
        if resp.status_code != 200: return []
        data = resp.json()
        if data.get('code') != 0:
            logger.error(f"API Error: {data.get('message')}")
            return []
        return data.get('files', [])
    except Exception as e:
        logger.error(f"Failed to get file list: {e}")
        return []

def download_single_file(file_url: str, target_dir: str) -> bool:
    try:
        resp = requests.get(file_url, timeout=60)
        if resp.status_code != 200: return False
        
        # Determine relative path by finding draft_id in URL
        parsed = urlparse(file_url)
        parts = parsed.path.split('/')
        
        # Find draft_id part (format: 2025...)
        draft_idx = -1
        for i, part in enumerate(parts):
            if re.match(r'^\d{8,}', part):
                draft_idx = i
                break
        
        rel_path = os.path.join(*(parts[draft_idx+1:])) if draft_idx != -1 else parts[-1]
        full_path = os.path.join(target_dir, rel_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        
        with open(full_path, 'wb') as f:
            f.write(resp.content)
            
        if full_path.endswith(('.json')):
            update_json_paths(full_path, target_dir)
            
        return True
    except Exception as e:
        logger.error(f"Failed to download {file_url}: {e}")
        return False

def update_json_paths(path: str, target_dir: str):
    """Convert remote Linux paths in JSON to local Windows paths."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        draft_id = os.path.basename(target_dir)
        remote_prefix = f"/app/output/draft/{draft_id}/"
        local_prefix = target_dir.replace('/', os.sep) + os.sep
        
        def walk(obj):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if isinstance(v, str) and v.startswith(remote_prefix):
                        obj[k] = local_prefix + v[len(remote_prefix):].replace('/', os.sep)
                    else:
                        walk(v)
            elif isinstance(obj, list):
                for i in range(len(obj)):
                    if isinstance(obj[i], str) and obj[i].startswith(remote_prefix):
                        obj[i] = local_prefix + obj[i][len(remote_prefix):].replace('/', os.sep)
                    else:
                        walk(obj[i])
        
        walk(data)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Failed to update JSON paths in {path}: {e}")

def trigger_directory_scan(path: str):
    """Trick OS/App into scanning directory using a temp copy operation."""
    if os.name == 'nt' and os.path.exists(path):
        tmp = path + ".tmp"
        try:
            subprocess.run(["robocopy", path, tmp, "/E", "/R:0", "/W:0", "/NP", "/NJH", "/NJS"], capture_output=True)
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)
        except Exception:
            pass
