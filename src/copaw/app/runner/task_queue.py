# -*- coding: utf-8 -*-
"""Task Queue for CoPaw.

Persistent task queue with crash recovery support.

Features:
- Memory + disk dual-write
- Crash recovery from persistent storage
- Task status tracking
- LRU completion cache (keeps last 100 completed tasks)

Example:
    >>> from copaw.app.runner.task_queue import TaskQueue, TaskSpec, TaskType
    >>>
    >>> queue = TaskQueue()
    >>> await queue.load_from_disk()  # Recover from disk on startup
    >>>
    >>> # Enqueue a task
    >>> task = TaskSpec(
    ...     user_id="user123",
    ...     channel="dingtalk",
    ...     session_id="session456",
    ...     type=TaskType.INSTRUCTION,
    ...     query="Create a cron job",
    ... )
    >>> await queue.enqueue(task)
    >>>
    >>> # Dequeue for processing
    >>> task = await queue.dequeue()
    >>> await queue.complete(task.id, "Task completed successfully")
"""
import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict

from .task_models import TaskSpec, TaskStatus, TaskType

logger = logging.getLogger(__name__)

__all__ = ["TaskQueue"]


class TaskQueue:
    """Persistent task queue for CoPaw.

    This queue provides:
    - Async enqueue/dequeue operations
    - Automatic persistence to disk
    - Crash recovery (reload pending/processing tasks on startup)
    - LRU cache for completed tasks

    Attributes:
        save_dir: Directory where task files are stored
    """

    def __init__(self, save_dir: str = "~/.copaw/tasks"):
        """Initialize TaskQueue.

        Args:
            save_dir: Directory to store task files
        """
        self.save_dir = Path(save_dir).expanduser()
        self.save_dir.mkdir(parents=True, exist_ok=True)

        # Memory queues
        self._pending_queue: asyncio.Queue[TaskSpec] = asyncio.Queue()
        self._processing: Dict[str, TaskSpec] = {}
        self._completed: Dict[str, TaskSpec] = {}  # LRU cache

        # Persistence files
        self._pending_file = self.save_dir / "pending.json"
        self._processing_file = self.save_dir / "processing.json"
        self._completed_file = self.save_dir / "completed.json"

        # Lock for thread safety
        self._lock = asyncio.Lock()

    async def load_from_disk(self) -> None:
        """Load tasks from disk (called on startup for crash recovery).

        Recovers:
        - Pending tasks: Re-queued for processing
        - Processing tasks: Marked as REPROCESSING with incremented retry count
        """
        import logging
        logger = logging.getLogger(__name__)

        async with self._lock:
            # Recover pending
            if self._pending_file.exists():
                try:
                    data = json.loads(self._pending_file.read_text(encoding="utf-8"))
                    for task_data in data.get("tasks", []):
                        task = TaskSpec(**task_data)
                        await self._pending_queue.put(task)
                except (json.JSONDecodeError, KeyError) as e:
                    logger.error(f"Failed to load pending tasks: {e}")

            # Recover processing (mark for reprocessing)
            if self._processing_file.exists():
                try:
                    data = json.loads(self._processing_file.read_text(encoding="utf-8"))
                    for task_data in data.get("tasks", []):
                        task = TaskSpec(**task_data)
                        # Skip tasks that have exceeded max retries
                        if task.retry_count >= task.max_retries:
                            logger.warning(
                                f"Skipping recovery of task {task.id}: "
                                f"retry_count ({task.retry_count}) >= max_retries ({task.max_retries})"
                            )
                            continue
                        task.status = TaskStatus.REPROCESSING
                        task.retry_count += 1
                        await self._pending_queue.put(task)
                except (json.JSONDecodeError, KeyError) as e:
                    logger.error(f"Failed to load processing tasks: {e}")

            # Load completed for reference (optional)
            if self._completed_file.exists():
                try:
                    data = json.loads(self._completed_file.read_text(encoding="utf-8"))
                    for task_data in data.get("tasks", []):
                        task = TaskSpec(**task_data)
                        self._completed[task.id] = task
                except (json.JSONDecodeError, KeyError) as e:
                    logger.error(f"Failed to load completed tasks: {e}")

    async def enqueue(self, task: TaskSpec) -> None:
        """Enqueue a task for processing.

        Args:
            task: Task to enqueue
        """
        # Skip if task is already completed (processed in real-time)
        if task.id in self._completed:
            logger.debug(f"Skipping enqueue task {task.id}: already completed")
            return

        logger.info(f"TaskQueue: Enqueueing task {task.id}")
        await self._pending_queue.put(task)
        logger.debug(f"TaskQueue: Task {task.id} put in pending queue, queue size: {self._pending_queue.qsize()}")
        # Persist without holding lock to avoid deadlock
        await self._persist_pending_simple()
        logger.info(f"TaskQueue: Task {task.id} enqueued and persisted")

    async def dequeue(self) -> Optional[TaskSpec]:
        """Dequeue a task for processing.

        Returns:
            Next task to process, or None if queue is empty
        """
        while True:
            try:
                task = await asyncio.wait_for(self._pending_queue.get(), timeout=0.1)

                # Skip if task is already completed (processed in real-time)
                if task.id in self._completed:
                    logger.debug(f"Skipping task {task.id}: already completed")
                    continue

                task.status = TaskStatus.PROCESSING
                task.started_at = datetime.now(timezone.utc)
                self._processing[task.id] = task
                logger.debug(f"Task {task.id} dequeued and added to _processing")
                # Persist without holding lock to avoid deadlock
                await self._persist_processing_simple()
                return task
            except asyncio.TimeoutError:
                return None

    async def complete(self, task_id: str, result: str) -> None:
        """Mark a task as completed.

        Args:
            task_id: Task ID to complete
            result: Task result (LLM response)
        """
        logger.info(f"Task {task_id}: complete() STARTED")
        async with self._lock:
            logger.info(f"Task {task_id}: complete() acquired lock, in _processing: {task_id in self._processing}")
            if task_id not in self._processing:
                logger.warning(f"Task {task_id}: Not in _processing, cannot complete")
                return

            task = self._processing[task_id]
            task.status = TaskStatus.WAITING_VERIFICATION
            task.llm_response = result
            task.completed_at = datetime.now(timezone.utc)

            del self._processing[task_id]
            self._completed[task_id] = task
            logger.info(f"Task {task_id}: Moved from _processing to _completed")
            # Note: Don't persist while holding lock - will persist after releasing

        # Persist after releasing lock to avoid blocking other operations
        await self._persist_all()
        logger.info(f"Task {task_id}: complete() FINISHED")

    async def fail(self, task_id: str, error: str) -> None:
        """Mark a task as failed.

        If retry count < max_retries, task is re-queued for reprocessing.
        Otherwise, task is moved to completed (failed state).

        Args:
            task_id: Task ID to fail
            error: Error message
        """
        async with self._lock:
            if task_id not in self._processing:
                return

            task = self._processing[task_id]
            task.status = TaskStatus.FAILED
            task.last_error = error
            task.retry_count += 1

            # Re-queue if can retry
            if task.retry_count < task.max_retries:
                task.status = TaskStatus.PENDING
                await self._pending_queue.put(task)
            else:
                del self._processing[task_id]
                self._completed[task_id] = task
            # Note: Don't persist while holding lock

        # Persist after releasing lock to avoid blocking other operations
        await self._persist_all()

    async def mark_verified(self, task_id: str, success: bool, details: str = "") -> None:
        """Mark a task as verified.

        Args:
            task_id: Task ID to verify
            success: Whether verification passed
            details: Verification details
        """
        logger.info(f"Task {task_id}: mark_verified() STARTED (success={success})")
        async with self._lock:
            logger.info(f"Task {task_id}: mark_verified() acquired lock, in _completed: {task_id in self._completed}")
            if task_id not in self._completed:
                logger.warning(f"Task {task_id}: Not in _completed, cannot mark verified")
                return

            task = self._completed[task_id]
            logger.info(f"Task {task_id}: task.status={task.status.value}")
            if task.status == TaskStatus.WAITING_VERIFICATION:
                task.verification_result = success
                task.verification_details = details
                if success:
                    task.status = TaskStatus.COMPLETED
                else:
                    # Verification failed, may need reprocessing
                    task.status = TaskStatus.FAILED
                    task.last_error = details

                logger.info(f"Task {task_id}: status updated, will persist after releasing lock")
            # Note: Don't persist while holding lock - will persist after releasing

        # Persist after releasing lock to avoid blocking other operations
        await self._persist_all()
        logger.info(f"Task {task_id}: mark_verified() FINISHED")

    async def get_task(self, task_id: str) -> Optional[TaskSpec]:
        """Get a task by ID.

        Searches pending, processing and completed caches.

        Args:
            task_id: Task ID to get

        Returns:
            TaskSpec if found, None otherwise
        """
        async with self._lock:
            # Search in processing
            if task_id in self._processing:
                return self._processing[task_id]
            # Search in completed
            if task_id in self._completed:
                return self._completed[task_id]

            # Search in pending queue
            pending_tasks = []
            while True:
                try:
                    task = self._pending_queue.get_nowait()
                    pending_tasks.append(task)
                    if task.id == task_id:
                        # Found it, re-queue all tasks and return
                        for t in pending_tasks:
                            self._pending_queue.put_nowait(t)
                        return task
                except asyncio.QueueEmpty:
                    break
            # Re-queue all pending tasks
            for task in pending_tasks:
                self._pending_queue.put_nowait(task)

            return None

    async def list_pending(self) -> List[TaskSpec]:
        """List all pending tasks (for debugging)."""
        tasks = []
        async with self._lock:
            # Drain the queue first, then re-queue all items
            while True:
                try:
                    task = self._pending_queue.get_nowait()
                    tasks.append(task)
                except asyncio.QueueEmpty:
                    break
            # Re-queue all tasks
            for task in tasks:
                self._pending_queue.put_nowait(task)
        return tasks

    async def list_processing(self) -> List[TaskSpec]:
        """List all processing tasks."""
        async with self._lock:
            return list(self._processing.values())

    async def list_completed(self, limit: int = 100) -> List[TaskSpec]:
        """List most recently completed tasks."""
        async with self._lock:
            sorted_completed = sorted(
                self._completed.values(),
                key=lambda t: t.completed_at.replace(tzinfo=None) if t.completed_at else datetime.min,
                reverse=True,
            )
            return sorted_completed[:limit]

    async def _persist_pending(self) -> None:
        """Persist pending tasks to disk."""
        tasks = []
        async with self._lock:
            # Drain the queue to snapshot all pending tasks
            # We need to re-queue them after persisting
            while True:
                try:
                    task = self._pending_queue.get_nowait()
                    tasks.append(task)
                except asyncio.QueueEmpty:
                    break
            # Re-queue all tasks after snapshot
            for task in tasks:
                self._pending_queue.put_nowait(task)

        data = {"version": 1, "tasks": [t.model_dump(mode="json") for t in tasks]}
        await self._atomic_write(self._pending_file, data)

    async def _persist_processing(self) -> None:
        """Persist processing tasks to disk."""
        async with self._lock:
            data = {
                "version": 1,
                "tasks": [t.model_dump(mode="json") for t in self._processing.values()],
            }
        await self._atomic_write(self._processing_file, data)

    async def _persist_completed(self) -> None:
        """Persist completed tasks to disk (LRU, keep last 100)."""
        async with self._lock:
            # Keep only last 100
            if len(self._completed) > 100:
                sorted_tasks = sorted(
                    self._completed.values(),
                    key=lambda t: t.completed_at.replace(tzinfo=None) if t.completed_at else datetime.min,
                    reverse=True,
                )
                to_remove = sorted_tasks[100:]
                for task in to_remove:
                    del self._completed[task.id]

            data = {
                "version": 1,
                "tasks": [t.model_dump(mode="json") for t in self._completed.values()],
            }
        await self._atomic_write(self._completed_file, data)

    async def _persist_pending_simple(self) -> None:
        """Persist pending tasks to disk (no lock - caller must not hold lock)."""
        tasks = []
        # Drain the queue to snapshot all pending tasks
        while True:
            try:
                task = self._pending_queue.get_nowait()
                tasks.append(task)
            except asyncio.QueueEmpty:
                break
        # Re-queue all tasks after snapshot
        for task in tasks:
            self._pending_queue.put_nowait(task)

        data = {"version": 1, "tasks": [t.model_dump(mode="json") for t in tasks]}
        await self._atomic_write(self._pending_file, data)

    async def _persist_processing_simple(self) -> None:
        """Persist processing tasks to disk (no lock - caller must not hold lock)."""
        data = {
            "version": 1,
            "tasks": [t.model_dump(mode="json") for t in self._processing.values()],
        }
        await self._atomic_write(self._processing_file, data)

    async def _persist_all(self) -> None:
        """Persist all task states to disk.

        This method prepares data while holding the lock, then releases
        the lock before doing async file I/O to prevent blocking.
        """
        # Prepare data while holding lock
        async with self._lock:
            pending_data, processing_data, completed_data = self._prepare_persist_data_sync()

        # Write to disk WITHOUT holding lock (prevents blocking)
        await asyncio.gather(
            self._atomic_write(self._pending_file, pending_data),
            self._atomic_write(self._processing_file, processing_data),
            self._atomic_write(self._completed_file, completed_data),
        )

    def _prepare_persist_data_sync(self) -> tuple:
        """Prepare persistence data synchronously (lock must be held by caller).

        This is a synchronous version that doesn't use await, so it can be
        called while holding the lock without blocking other operations.
        """
        # Drain pending queue to snapshot
        pending_tasks = []
        while True:
            try:
                task = self._pending_queue.get_nowait()
                pending_tasks.append(task)
            except asyncio.QueueEmpty:
                break
        # Re-queue all tasks
        for task in pending_tasks:
            self._pending_queue.put_nowait(task)

        pending_data = {"version": 1, "tasks": [t.model_dump(mode="json") for t in pending_tasks]}
        processing_data = {
            "version": 1,
            "tasks": [t.model_dump(mode="json") for t in self._processing.values()],
        }

        # Trim completed to last 100
        completed_values = list(self._completed.values())
        if len(completed_values) > 100:
            sorted_completed = sorted(
                completed_values,
                key=lambda t: t.completed_at.replace(tzinfo=None) if t.completed_at else datetime.min,
                reverse=True,
            )
            completed_values = sorted_completed[:100]

        completed_data = {"version": 1, "tasks": [t.model_dump(mode="json") for t in completed_values]}
        return pending_data, processing_data, completed_data

    async def _atomic_write(self, path: Path, data: dict) -> None:
        """Write data to file atomically (temp file + rename)."""
        import asyncio
        tmp_path = path.with_suffix(".tmp")
        content = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True)
        # Run synchronous file I/O in thread pool to avoid blocking event loop
        await asyncio.to_thread(_write_file_atomic, tmp_path, content, path)

    async def clear_all(self) -> None:
        """Clear all tasks (use with caution)."""
        async with self._lock:
            self._processing.clear()
            self._completed.clear()
            # Clear pending queue
            while not self._pending_queue.empty():
                try:
                    self._pending_queue.get_nowait()
                except asyncio.QueueEmpty:
                    break

        # Persist to disk (simple approach - write empty lists)
        import json
        from pathlib import Path

        for fname in ['pending_tasks.json', 'processing_tasks.json', 'completed_tasks.json']:
            fpath = self._pending_file.parent / fname
            try:
                data = {"version": 1, "tasks": []}
                await asyncio.to_thread(
                    lambda p=fpath: p.write_text(json.dumps(data, indent=2), encoding='utf-8')
                )
            except Exception:
                pass

    async def remove_completed(self, task_id: str) -> bool:
        """Remove a completed task from the completed cache.

        Args:
            task_id: Task ID to remove

        Returns:
            True if task was removed, False if not found
        """
        async with self._lock:
            if task_id in self._completed:
                del self._completed[task_id]
                await self._persist_completed()
                return True
            return False


def _write_file_atomic(tmp_path: Path, content: str, final_path: Path) -> None:
    """Synchronous file write helper for atomic writes."""
    tmp_path.write_text(content, encoding="utf-8")
    tmp_path.replace(final_path)
