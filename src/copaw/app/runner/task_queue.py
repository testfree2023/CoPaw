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
from pathlib import Path
from typing import Optional, List, Dict

from .task_models import TaskSpec, TaskStatus, TaskType

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
        async with self._lock:
            # Recover pending
            if self._pending_file.exists():
                try:
                    data = json.loads(self._pending_file.read_text(encoding="utf-8"))
                    for task_data in data.get("tasks", []):
                        task = TaskSpec(**task_data)
                        await self._pending_queue.put(task)
                except (json.JSONDecodeError, KeyError) as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Failed to load pending tasks: {e}")

            # Recover processing (mark for reprocessing)
            if self._processing_file.exists():
                try:
                    data = json.loads(self._processing_file.read_text(encoding="utf-8"))
                    for task_data in data.get("tasks", []):
                        task = TaskSpec(**task_data)
                        task.status = TaskStatus.REPROCESSING
                        task.retry_count += 1
                        await self._pending_queue.put(task)
                except (json.JSONDecodeError, KeyError) as e:
                    logger = logging.getLogger(__name__)
                    logger.error(f"Failed to load processing tasks: {e}")

            # Load completed for reference (optional)
            if self._completed_file.exists():
                try:
                    data = json.loads(self._completed_file.read_text(encoding="utf-8"))
                    for task_data in data.get("tasks", []):
                        task = TaskSpec(**task_data)
                        self._completed[task.id] = task
                except (json.JSONDecodeError, KeyError) as e:
                    logger = logging.getLogger(__name__)
                    logger.error(f"Failed to load completed tasks: {e}")

    async def enqueue(self, task: TaskSpec) -> None:
        """Enqueue a task for processing.

        Args:
            task: Task to enqueue
        """
        await self._pending_queue.put(task)
        await self._persist_pending()

    async def dequeue(self) -> Optional[TaskSpec]:
        """Dequeue a task for processing.

        Returns:
            Next task to process, or None if queue is empty
        """
        try:
            task = await asyncio.wait_for(self._pending_queue.get(), timeout=0.1)
            task.status = TaskStatus.PROCESSING
            task.started_at = datetime.utcnow()
            self._processing[task.id] = task
            await self._persist_processing()
            return task
        except asyncio.TimeoutError:
            return None

    async def complete(self, task_id: str, result: str) -> None:
        """Mark a task as completed.

        Args:
            task_id: Task ID to complete
            result: Task result (LLM response)
        """
        async with self._lock:
            if task_id not in self._processing:
                return

            task = self._processing[task_id]
            task.status = TaskStatus.WAITING_VERIFICATION
            task.llm_response = result
            task.completed_at = datetime.utcnow()

            del self._processing[task_id]
            self._completed[task_id] = task

            await self._persist_all()

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

            await self._persist_all()

    async def mark_verified(self, task_id: str, success: bool, details: str = "") -> None:
        """Mark a task as verified.

        Args:
            task_id: Task ID to verify
            success: Whether verification passed
            details: Verification details
        """
        async with self._lock:
            if task_id not in self._completed:
                return

            task = self._completed[task_id]
            if task.status == TaskStatus.WAITING_VERIFICATION:
                task.verification_result = success
                task.verification_details = details
                if success:
                    task.status = TaskStatus.COMPLETED
                else:
                    # Verification failed, may need reprocessing
                    task.status = TaskStatus.FAILED
                    task.last_error = details

                await self._persist_all()

    async def get_task(self, task_id: str) -> Optional[TaskSpec]:
        """Get a task by ID.

        Searches processing and completed caches.

        Args:
            task_id: Task ID to get

        Returns:
            TaskSpec if found, None otherwise
        """
        async with self._lock:
            if task_id in self._processing:
                return self._processing[task_id]
            if task_id in self._completed:
                return self._completed[task_id]
            return None

    async def list_pending(self) -> List[TaskSpec]:
        """List all pending tasks (for debugging)."""
        tasks = []
        async with self._lock:
            while not self._pending_queue.empty():
                task = self._pending_queue.get_nowait()
                tasks.append(task)
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
                key=lambda t: t.completed_at or datetime.min,
                reverse=True,
            )
            return sorted_completed[:limit]

    async def _persist_pending(self) -> None:
        """Persist pending tasks to disk."""
        tasks = []
        async with self._lock:
            while not self._pending_queue.empty():
                task = self._pending_queue.get_nowait()
                tasks.append(task)
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
                    key=lambda t: t.completed_at or datetime.min,
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

    async def _persist_all(self) -> None:
        """Persist all task states to disk."""
        await asyncio.gather(
            self._persist_pending(),
            self._persist_processing(),
            self._persist_completed(),
        )

    async def _atomic_write(self, path: Path, data: dict) -> None:
        """Write data to file atomically (temp file + rename)."""
        tmp_path = path.with_suffix(".tmp")
        tmp_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        tmp_path.replace(path)

    async def clear_all(self) -> None:
        """Clear all tasks (use with caution)."""
        async with self._lock:
            self._processing.clear()
            self._completed.clear()
            # Clear pending queue
            while not self._pending_queue.empty():
                self._pending_queue.get_nowait()
            await self._persist_all()


# Import datetime at module level
from datetime import datetime
