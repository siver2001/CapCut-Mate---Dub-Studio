"""
Video generation async task queue manager.
Supports task queuing, status tracking, and results query.
"""
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from enum import Enum
from typing import Dict, Optional, Tuple, Any
from dataclasses import dataclass
import os
import sys
import json
import shutil
from src.utils.logger import logger
from src.utils import helper
import src.pyJianYingDraft as draft
import config

# Conditional import for UI automation on Windows
try:
    from uiautomation import UIAutomationInitializerInThread
except ImportError:
    class UIAutomationInitializerInThread:
        def __enter__(self): pass
        def __exit__(self, *args): pass

class TaskStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class VideoGenTask:
    draft_url: str
    draft_id: str
    status: TaskStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    video_url: str = ""
    error_message: str = ""
    progress: int = 0
    api_key: Optional[str] = None
    outfile: str = ""

class VideoGenTaskManager:
    """Singleton manager for video generation tasks."""
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        self._initialized = True
        self.tasks: Dict[str, VideoGenTask] = {}
        self.task_queue: asyncio.Queue = asyncio.Queue()
        
        workers = min(32, (os.cpu_count() or 1) + 4)
        self._download_executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="draft_dl")
        self._upload_executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="cos_upload")
        self.export_video_lock = threading.Lock()
        
        self.worker_thread: Optional[threading.Thread] = None
        self.stop_flag = threading.Event()
        logger.info("VideoGenTaskManager initialized")

    def submit_task(self, draft_url: str, api_key: str = None) -> None:
        """Submit a new task to the queue."""
        draft_id = helper.get_url_param(draft_url, "draft_id")
        if not draft_id:
            raise ValueError("Invalid draft URL")

        if draft_url in self.tasks:
            if self.tasks[draft_url].status in [TaskStatus.PENDING, TaskStatus.PROCESSING]:
                logger.info(f"Task already active for: {draft_url}")
                return

        task = VideoGenTask(
            draft_url=draft_url,
            draft_id=draft_id,
            status=TaskStatus.PENDING,
            created_at=datetime.now(),
            api_key=api_key
        )
        self.tasks[draft_url] = task
        self._add_task_to_queue_sync(task)
        self._ensure_worker_running()

    def _add_task_to_queue_sync(self, task: VideoGenTask):
        """Thread-safe submission to asyncio queue."""
        try:
            loop = asyncio.get_running_loop()
            asyncio.run_coroutine_threadsafe(self.task_queue.put(task), loop)
        except RuntimeError:
            # No loop running, start a temporary one in a thread
            def run_in_new_loop():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(self.task_queue.put(task))
                loop.close()
            threading.Thread(target=run_in_new_loop, daemon=True).start()

    def get_task_status(self, draft_url: str) -> Optional[Dict[str, Any]]:
        """Get current status of a specific task."""
        task = self.tasks.get(draft_url)
        if not task: return None
        return {
            "draft_url": task.draft_url,
            "status": task.status.value,
            "progress": task.progress,
            "video_url": task.video_url,
            "error_message": task.error_message,
            "created_at": task.created_at.isoformat(),
            "started_at": task.started_at.isoformat() if task.started_at else None,
            "completed_at": task.completed_at.isoformat() if task.completed_at else None
        }

    def _ensure_worker_running(self):
        if not self.worker_thread or not self.worker_thread.is_alive():
            self.stop_flag.clear()
            self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
            self.worker_thread.start()

    def _worker_loop(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._async_worker_loop())
        finally:
            loop.close()

    async def _async_worker_loop(self):
        while not self.stop_flag.is_set():
            try:
                task = await asyncio.wait_for(self.task_queue.get(), timeout=1.0)
                asyncio.create_task(self._process_task(task))
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Worker loop error: {e}")
                await asyncio.sleep(1)

    async def _process_task(self, task: VideoGenTask):
        """Full pipeline: download -> export -> upload -> cleanup."""
        logger.info(f"Processing task: {task.draft_id}")
        task.status = TaskStatus.PROCESSING
        task.started_at = datetime.now()
        task.progress = 10
        loop = asyncio.get_running_loop()

        try:
            # Phase 1: Download
            error = await loop.run_in_executor(self._download_executor, self._phase_download, task)
            if error:
                self._fail_task(task, error)
                return

            # Phase 2: Export (Serialized via lock)
            error = await loop.run_in_executor(None, self._phase_export, task)
            if error:
                self._fail_task(task, error)
                return

            # Phase 3: Upload and Cleanup
            video_url, error = await loop.run_in_executor(self._upload_executor, self._phase_finalize, task)
            if video_url:
                task.status = TaskStatus.COMPLETED
                task.video_url = video_url
                task.progress = 100
                logger.info(f"Task finished: {task.draft_id}")
            else:
                self._fail_task(task, error)

        except Exception as e:
            self._fail_task(task, str(e))
        finally:
            task.completed_at = datetime.now()

    def _fail_task(self, task: VideoGenTask, error: str):
        task.status = TaskStatus.FAILED
        task.error_message = error
        task.progress = 0
        logger.error(f"Task failed: {task.draft_id}, error: {error}")

    def _phase_download(self, task: VideoGenTask) -> str:
        if not sys.platform.startswith("win"):
            return "Export features only available on Windows"
        
        task.progress = 20
        task.outfile = os.path.join(config.DRAFT_DIR, f"{helper.gen_unique_id()}.mp4")
        
        from src.utils.draft_downloader import download_draft
        if not download_draft(task.draft_url):
            return "Failed to download draft"
        
        # Check duration
        path = os.path.join(config.DRAFT_SAVE_PATH, task.draft_id, "draft_content.json")
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = json.load(f)
                if content.get("duration", 0) <= 0:
                    return "Draft duration is zero"
        except Exception:
            return "Failed to read draft metadata"
            
        task.progress = 40
        return ""

    def _phase_export(self, task: VideoGenTask) -> str:
        with self.export_video_lock:
            task.progress = 50
            try:
                if draft.JianyingController is None:
                    return "CapCut controller dependency missing"
                
                with UIAutomationInitializerInThread():
                    ctrl = draft.JianyingController()
                    task.progress = 70
                    ctrl.export_draft(task.draft_id, task.outfile)
                
                if not os.path.exists(task.outfile):
                    return "Export file not generated"
                return ""
            except Exception as e:
                return f"Export error: {str(e)}"

    def _phase_finalize(self, task: VideoGenTask) -> Tuple[str, str]:
        task.progress = 90
        try:
            # Upload
            from src.utils.cos import cos_upload_file
            url = cos_upload_file(task.outfile)
            
            # Charge
            if config.ENABLE_APIKEY and task.api_key:
                from src.utils.media import get_media_duration
                from src.utils.points import deduct_user_points
                duration_us = get_media_duration(task.outfile)
                if duration_us:
                    sec = duration_us / 1_000_000
                    deduct_user_points(task.api_key, sec * 0.01, f"Export {sec:.2f}s")
            
            # Cleanup
            if os.path.exists(task.outfile): os.remove(task.outfile)
            shutil.rmtree(os.path.join(config.DRAFT_SAVE_PATH, task.draft_id), ignore_errors=True)
            
            return url, ""
        except Exception as e:
            return "", str(e)

    def stop(self):
        self.stop_flag.set()
        if self.worker_thread: self.worker_thread.join(timeout=5)
        self._download_executor.shutdown(wait=False)
        self._upload_executor.shutdown(wait=False)

task_manager = VideoGenTaskManager()
