import asyncio
import time
from typing import Dict, Optional
from src.utils.logger import logger

class DraftLockManager:
    _instance = None
    _init_lock = asyncio.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, '_initialized') and self._initialized:
            return
        self._locks: Dict[str, asyncio.Lock] = {}
        self._lock_counts: Dict[str, int] = {}
        self._lock_owner: Dict[str, str] = {}
        self._lock_acquired_at: Dict[str, float] = {}
        self._manager_lock = asyncio.Lock()
        self._initialized = True
        logger.info('DraftLockManager initialized')

    async def acquire_lock(self, draft_id: str, timeout: Optional[float]=None) -> bool:
        async with self._manager_lock:
            if draft_id not in self._locks:
                self._locks[draft_id] = asyncio.Lock()
                self._lock_counts[draft_id] = 0
            lock = self._locks[draft_id]
        wait_started_at = time.monotonic()
        try:
            if timeout is not None:
                await asyncio.wait_for(lock.acquire(), timeout=timeout)
            else:
                await lock.acquire()
            async with self._manager_lock:
                self._lock_counts[draft_id] = self._lock_counts.get(draft_id, 0) + 1
                task = asyncio.current_task()
                task_name = task.get_name() if task and hasattr(task, 'get_name') else None
                self._lock_owner[draft_id] = task_name or 'unknown'
                self._lock_acquired_at[draft_id] = time.monotonic()
            waited = time.monotonic() - wait_started_at
            logger.info(f'Lock acquired for draft_id: {draft_id}, waited: {waited:.3f}s, count: {self._lock_counts[draft_id]}')
            return True
        except asyncio.TimeoutError:
            waited = time.monotonic() - wait_started_at
            async with self._manager_lock:
                owner = self._lock_owner.get(draft_id)
                acquired_at = self._lock_acquired_at.get(draft_id)
                held_for = time.monotonic() - acquired_at if acquired_at else None
                count = self._lock_counts.get(draft_id, 0)
                locked = self._locks.get(draft_id).locked() if draft_id in self._locks else False
                if held_for is not None:
                    logger.warning(f'Timeout waiting for lock on draft_id: {draft_id}, waited: {waited:.3f}s, locked: {locked}, holders: {count}, owner: {owner}, held_for: {held_for:.3f}s')
                else:
                    logger.warning(f'Timeout waiting for lock on draft_id: {draft_id}, waited: {waited:.3f}s, locked: {locked}, holders: {count}, owner: {owner}')
            raise

    async def release_lock(self, draft_id: str) -> None:
        async with self._manager_lock:
            if draft_id not in self._locks:
                raise KeyError(f'No lock found for draft_id: {draft_id}')
            lock = self._locks[draft_id]
            self._lock_counts[draft_id] = max(0, self._lock_counts.get(draft_id, 0) - 1)
            acquired_at = self._lock_acquired_at.get(draft_id)
            owner = self._lock_owner.get(draft_id)
        try:
            lock.release()
            held_for = time.monotonic() - acquired_at if acquired_at else None
            logger.info(f'Lock released for draft_id: {draft_id}, held_for: {held_for:.3f}s, owner: {owner}' if held_for is not None else f'Lock released for draft_id: {draft_id}, owner: {owner}')
        except RuntimeError as e:
            logger.error(f'Failed to release lock for draft_id {draft_id}: {str(e)}')
            raise
        finally:
            async with self._manager_lock:
                lock_obj = self._locks.get(draft_id)
                if lock_obj is not None:
                    waiters = getattr(lock_obj, '_waiters', None)
                    has_waiters = bool(waiters) if waiters is not None else False
                    if self._lock_counts.get(draft_id, 0) <= 0 and (not lock_obj.locked()) and (not has_waiters):
                        self._locks.pop(draft_id, None)
                        self._lock_counts.pop(draft_id, None)
                        self._lock_owner.pop(draft_id, None)
                        self._lock_acquired_at.pop(draft_id, None)

    def is_locked(self, draft_id: str) -> bool:
        if draft_id not in self._locks:
            return False
        return self._locks[draft_id].locked()

    def get_lock_count(self, draft_id: str) -> int:
        return self._lock_counts.get(draft_id, 0)

    def get_all_locked_drafts(self) -> list:
        return [draft_id for draft_id, lock in self._locks.items() if lock.locked()]

    async def clear_all_locks(self) -> None:
        async with self._manager_lock:
            released_count = len(self._locks)
            self._locks.clear()
            self._lock_counts.clear()
            if released_count > 0:
                logger.warning(f'Cleared all locks, released {released_count} locks')

    def get_stats(self) -> dict:
        locked_count = sum((1 for lock in self._locks.values() if lock.locked()))
        return {'total_locks': len(self._locks), 'locked_drafts': locked_count, 'total_holders': sum(self._lock_counts.values())}
_draft_lock_manager: Optional[DraftLockManager] = None

def get_draft_lock_manager() -> DraftLockManager:
    global _draft_lock_manager
    if _draft_lock_manager is None:
        _draft_lock_manager = DraftLockManager()
    return _draft_lock_manager