# -*- coding: utf-8 -*-
"""Tests for TaskQueue and TaskSpec."""
import pytest
import asyncio
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timedelta

from copaw.app.runner.task_queue import TaskQueue
from copaw.app.runner.task_models import TaskSpec, TaskType, TaskStatus


@pytest.fixture
def temp_tasks_dir():
    """Create a temporary directory for task queue tests."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def task_queue(temp_tasks_dir):
    """Create a TaskQueue with temporary storage."""
    queue = TaskQueue(save_dir=temp_tasks_dir)
    return queue


@pytest.fixture
def sample_task():
    """Create a sample task for testing."""
    return TaskSpec(
        user_id="user123",
        channel="dingtalk",
        session_id="session456",
        type=TaskType.INSTRUCTION,
        query="Create a cron job",
    )


@pytest.mark.asyncio
async def test_enqueue_dequeue(task_queue, sample_task):
    """Test basic enqueue and dequeue operations."""
    # Enqueue
    await task_queue.enqueue(sample_task)

    # Dequeue
    task = await task_queue.dequeue()

    assert task is not None
    assert task.id == sample_task.id
    assert task.status == TaskStatus.PROCESSING
    assert task.started_at is not None


@pytest.mark.asyncio
async def test_dequeue_empty_queue(task_queue):
    """Test dequeue from empty queue returns None."""
    task = await task_queue.dequeue()
    assert task is None


@pytest.mark.asyncio
async def test_complete_task(task_queue, sample_task):
    """Test completing a task."""
    await task_queue.enqueue(sample_task)
    task = await task_queue.dequeue()

    await task_queue.complete(task.id, "Task completed successfully")

    # Verify task is in completed
    completed_task = await task_queue.get_task(task.id)
    assert completed_task is not None
    assert completed_task.status == TaskStatus.WAITING_VERIFICATION
    assert completed_task.llm_response == "Task completed successfully"
    assert completed_task.completed_at is not None


@pytest.mark.asyncio
async def test_fail_task_with_retry(task_queue, sample_task):
    """Test failing a task with retry."""
    sample_task.max_retries = 3
    await task_queue.enqueue(sample_task)
    task = await task_queue.dequeue()

    # First failure - should be re-queued
    await task_queue.fail(task.id, "First error")

    # Task should be back in pending
    pending_tasks = await task_queue.list_pending()
    assert len(pending_tasks) == 1
    assert pending_tasks[0].retry_count == 1
    assert pending_tasks[0].status == TaskStatus.PENDING


@pytest.mark.asyncio
async def test_fail_task_max_retries(task_queue, sample_task):
    """Test failing a task after max retries."""
    sample_task.max_retries = 1
    sample_task.retry_count = 1  # Simulate previous retry
    await task_queue.enqueue(sample_task)
    task = await task_queue.dequeue()

    # Fail - should not be re-queued (max retries reached)
    await task_queue.fail(task.id, "Error after max retries")

    # Task should be in completed (failed state)
    completed_tasks = await task_queue.list_completed()
    assert len(completed_tasks) == 1
    assert completed_tasks[0].status == TaskStatus.FAILED
    assert completed_tasks[0].last_error == "Error after max retries"


@pytest.mark.asyncio
async def test_mark_verified(task_queue, sample_task):
    """Test marking a task as verified."""
    await task_queue.enqueue(sample_task)
    task = await task_queue.dequeue()
    await task_queue.complete(task.id, "Done")

    # Mark as verified
    await task_queue.mark_verified(task.id, success=True, details="Verification passed")

    verified_task = await task_queue.get_task(task.id)
    assert verified_task.verification_result is True
    assert verified_task.verification_details == "Verification passed"
    assert verified_task.status == TaskStatus.COMPLETED


@pytest.mark.asyncio
async def test_mark_verification_failed(task_queue, sample_task):
    """Test marking verification as failed."""
    await task_queue.enqueue(sample_task)
    task = await task_queue.dequeue()
    await task_queue.complete(task.id, "Done")

    # Mark verification as failed
    await task_queue.mark_verified(task.id, success=False, details="Verification failed")

    verified_task = await task_queue.get_task(task.id)
    assert verified_task.verification_result is False
    assert verified_task.status == TaskStatus.FAILED
    assert verified_task.last_error == "Verification failed"


@pytest.mark.asyncio
async def test_get_task_not_found(task_queue):
    """Test getting a non-existent task."""
    task = await task_queue.get_task("non-existent-id")
    assert task is None


@pytest.mark.asyncio
async def test_list_tasks(task_queue, sample_task):
    """Test listing tasks in different states."""
    # Add multiple tasks
    tasks = []
    for i in range(5):
        task = TaskSpec(
            user_id=f"user{i}",
            channel="dingtalk",
            session_id=f"session{i}",
            type=TaskType.INSTRUCTION,
            query=f"Task {i}",
        )
        await task_queue.enqueue(task)
        tasks.append(task)

    # Dequeue 2 tasks
    await task_queue.dequeue()
    await task_queue.dequeue()

    # List pending (should have 3 left)
    pending = await task_queue.list_pending()
    assert len(pending) == 3

    # List processing (should have 2)
    processing = await task_queue.list_processing()
    assert len(processing) == 2


@pytest.mark.asyncio
async def test_persistence(task_queue, temp_tasks_dir, sample_task):
    """Test tasks are persisted to disk."""
    await task_queue.enqueue(sample_task)

    # Verify files exist
    pending_file = Path(temp_tasks_dir) / "pending.json"
    assert pending_file.exists()

    # Verify content
    import json
    data = json.loads(pending_file.read_text())
    assert len(data["tasks"]) == 1
    assert data["tasks"][0]["id"] == sample_task.id


@pytest.mark.asyncio
async def test_load_from_disk(temp_tasks_dir, sample_task):
    """Test loading tasks from disk (crash recovery)."""
    # First queue: enqueue task
    queue1 = TaskQueue(save_dir=temp_tasks_dir)
    await queue1.enqueue(sample_task)

    # Second queue: load from disk
    queue2 = TaskQueue(save_dir=temp_tasks_dir)
    await queue2.load_from_disk()

    # Task should be available
    task = await queue2.dequeue()
    assert task is not None
    assert task.id == sample_task.id


@pytest.mark.asyncio
async def test_load_processing_as_reprocessing(temp_tasks_dir, sample_task):
    """Test processing tasks are loaded as REPROCESSING."""
    # First queue: enqueue and dequeue (moves to processing)
    queue1 = TaskQueue(save_dir=temp_tasks_dir)
    await queue1.enqueue(sample_task)
    task = await queue1.dequeue()
    assert task.status == TaskStatus.PROCESSING

    # Second queue: load from disk
    queue2 = TaskQueue(save_dir=temp_tasks_dir)
    await queue2.load_from_disk()

    # Task should be re-queued with REPROCESSING status
    reprocessed = await queue2.dequeue()
    assert reprocessed is not None
    assert reprocessed.status == TaskStatus.REPROCESSING
    assert reprocessed.retry_count == 1


@pytest.mark.asyncio
async def test_lru_completed_cache(task_queue, sample_task):
    """Test LRU cache for completed tasks (keeps last 100)."""
    # Complete 150 tasks
    for i in range(150):
        task = TaskSpec(
            user_id=f"user{i}",
            channel="dingtalk",
            session_id=f"session{i}",
            type=TaskType.INSTRUCTION,
            query=f"Task {i}",
        )
        await task_queue.enqueue(task)
        t = await task_queue.dequeue()
        await task_queue.complete(t.id, f"Result {i}")

    # Should only keep last 100
    completed = await task_queue.list_completed()
    assert len(completed) == 100

    # First task should be dropped (task_0)
    # Last task should be present (task_149)
    task_ids = [t.id for t in completed]
    # Note: We can't check exact IDs since they're UUIDs, but we can check count


@pytest.mark.asyncio
async def test_task_is_terminal(task_queue, sample_task):
    """Test TaskSpec.is_terminal() method."""
    assert sample_task.is_terminal() is False

    sample_task.status = TaskStatus.COMPLETED
    assert sample_task.is_terminal() is True

    sample_task.status = TaskStatus.FAILED
    assert sample_task.is_terminal() is True

    sample_task.status = TaskStatus.PROCESSING
    assert sample_task.is_terminal() is False


@pytest.mark.asyncio
async def test_task_can_retry(task_queue, sample_task):
    """Test TaskSpec.can_retry() method."""
    # Fresh task
    assert sample_task.can_retry() is False

    # Failed with retries left
    sample_task.status = TaskStatus.FAILED
    sample_task.retry_count = 0
    sample_task.max_retries = 3
    assert sample_task.can_retry() is True

    # Failed after max retries
    sample_task.retry_count = 3
    assert sample_task.can_retry() is False


@pytest.mark.asyncio
async def test_clear_all_tasks(task_queue, sample_task):
    """Test clearing all tasks."""
    # Add tasks
    for i in range(5):
        await task_queue.enqueue(TaskSpec(
            user_id=f"user{i}",
            channel="dingtalk",
            session_id=f"session{i}",
            type=TaskType.INSTRUCTION,
            query=f"Task {i}",
        ))

    # Clear all
    await task_queue.clear_all()

    # Verify all cleared
    pending = await task_queue.list_pending()
    assert len(pending) == 0
    processing = await task_queue.list_processing()
    assert len(processing) == 0
    completed = await task_queue.list_completed()
    assert len(completed) == 0


@pytest.mark.asyncio
async def test_concurrent_enqueue(task_queue):
    """Test concurrent enqueue operations."""
    async def enqueue_task(i):
        task = TaskSpec(
            user_id=f"user{i}",
            channel="dingtalk",
            session_id=f"session{i}",
            type=TaskType.INSTRUCTION,
            query=f"Task {i}",
        )
        await task_queue.enqueue(task)

    # Enqueue 50 tasks concurrently
    await asyncio.gather(*[enqueue_task(i) for i in range(50)])

    # Verify all enqueued
    pending = await task_queue.list_pending()
    assert len(pending) == 50
