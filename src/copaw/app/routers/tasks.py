# -*- coding: utf-8 -*-
"""Task management API router for CoPaw.

This module provides REST API endpoints for task management:
- List tasks
- Get task details
- Retry failed tasks
- Manually verify tasks
- Create tasks (from templates)
- Delete tasks
"""
import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..runner.task_models import TaskSpec, TaskType, TaskStatus
from ..runner.task_queue import TaskQueue

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tasks", tags=["tasks"])

# Global task queue reference (set during app initialization)
_task_queue: Optional[TaskQueue] = None


def set_task_queue(task_queue: TaskQueue) -> None:
    """Set task queue for API router.

    Args:
        task_queue: TaskQueue instance
    """
    global _task_queue
    _task_queue = task_queue
    logger.debug("Task queue set for API router")


class CreateTaskRequest(BaseModel):
    """Request body for creating a task."""
    user_id: str
    channel: str = "console"
    session_id: str
    query: str
    task_type: TaskType = TaskType.INSTRUCTION
    metadata: dict = Field(default_factory=dict)


class TaskListItem(BaseModel):
    """Task list item for API response."""
    id: str
    user_id: str
    channel: str
    session_id: str
    type: TaskType
    query: str
    status: TaskStatus
    created_at: str
    completed_at: Optional[str] = None
    verification_result: Optional[bool] = None

    class Config:
        json_encoders = {
            TaskType: lambda v: v.value,
            TaskStatus: lambda v: v.value,
        }


@router.get("", response_model=List[TaskListItem])
async def list_tasks(
    status: Optional[str] = None,
    task_type: Optional[str] = None,
    user_id: Optional[str] = None,
    channel: Optional[str] = None,
    limit: int = 50,
) -> List[TaskListItem]:
    """Get list of tasks with optional filtering.

    Args:
        status: Filter by task status (pending/completed/failed/etc.)
        task_type: Filter by task type (instruction/rule/conversation)
        user_id: Filter by user ID
        channel: Filter by channel
        limit: Maximum number of tasks to return

    Returns:
        List of task items
    """
    if _task_queue is None:
        raise HTTPException(status_code=503, detail="Task queue not initialized")

    tasks = []

    # Get tasks from all queues based on filters
    if status is None or status == "pending":
        pending = await _task_queue.list_pending()
        tasks.extend(pending)
    if status is None or status == "processing":
        processing = await _task_queue.list_processing()
        tasks.extend(processing)
    if status is None or status == "completed" or status == "failed":
        completed = await _task_queue.list_completed(limit=limit)
        tasks.extend(completed)

    # Apply filters
    filtered = []
    for task in tasks:
        if user_id and task.user_id != user_id:
            continue
        if channel and task.channel != channel:
            continue
        if task_type and task.type.value != task_type:
            continue
        if status and task.status.value != status:
            continue
        filtered.append(task)

    # Sort by created_at (newest first) and limit
    filtered.sort(key=lambda t: t.created_at, reverse=True)
    filtered = filtered[:limit]

    # Convert to response format
    return [
        TaskListItem(
            id=task.id,
            user_id=task.user_id,
            channel=task.channel,
            session_id=task.session_id,
            type=task.type,
            query=task.query,
            status=task.status,
            created_at=task.created_at.isoformat() if task.created_at else None,
            completed_at=task.completed_at.isoformat() if task.completed_at else None,
            verification_result=task.verification_result,
        )
        for task in filtered
    ]


@router.get("/{task_id}")
async def get_task(task_id: str) -> TaskSpec:
    """Get task details by ID.

    Args:
        task_id: Task ID

    Returns:
        Task specification
    """
    if _task_queue is None:
        raise HTTPException(status_code=503, detail="Task queue not initialized")

    # Search in all queues
    task = await _task_queue.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    return task


@router.post("/{task_id}/retry")
async def retry_task(task_id: str) -> dict:
    """Retry a failed task.

    Args:
        task_id: Task ID to retry

    Returns:
        Status message
    """
    if _task_queue is None:
        raise HTTPException(status_code=503, detail="Task queue not initialized")

    task = await _task_queue.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    if task.status != TaskStatus.FAILED:
        raise HTTPException(
            status_code=400,
            detail=f"Task {task_id} is not in FAILED state (current: {task.status.value})"
        )

    if not task.can_retry():
        raise HTTPException(
            status_code=400,
            detail=f"Task {task_id} has reached max retries"
        )

    # Reset task state and requeue
    task.status = TaskStatus.PENDING
    task.last_error = None
    await _task_queue.enqueue(task)

    logger.info(f"Task {task_id} requeued for retry")
    return {"status": "success", "message": f"Task {task_id} requeued"}


@router.post("/{task_id}/verify")
async def verify_task(task_id: str, success: bool, details: str = "") -> dict:
    """Manually verify a task.

    Args:
        task_id: Task ID to verify
        success: Whether verification succeeded
        details: Optional verification details

    Returns:
        Status message
    """
    if _task_queue is None:
        raise HTTPException(status_code=503, detail="Task queue not initialized")

    task = await _task_queue.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    if task.status != TaskStatus.WAITING_VERIFICATION:
        raise HTTPException(
            status_code=400,
            detail=f"Task {task_id} is not in WAITING_VERIFICATION state"
        )

    await _task_queue.mark_verified(task_id, success, details)

    logger.info(f"Task {task_id} manually verified: success={success}")
    return {"status": "success", "message": f"Task {task_id} verified"}


@router.post("", response_model=TaskSpec)
async def create_task(request: CreateTaskRequest) -> TaskSpec:
    """Create a new task manually (e.g., from template).

    Args:
        request: Task creation request

    Returns:
        Created task specification
    """
    if _task_queue is None:
        raise HTTPException(status_code=503, detail="Task queue not initialized")

    task = TaskSpec(
        user_id=request.user_id,
        channel=request.channel,
        session_id=request.session_id,
        type=request.task_type,
        query=request.query,
        status=TaskStatus.PENDING,
        metadata=request.metadata,
    )

    await _task_queue.enqueue(task)
    logger.info(f"Task created manually: {task.id} (type={request.task_type.value})")

    return task


@router.delete("/{task_id}")
async def delete_task(task_id: str) -> dict:
    """Delete a task.

    Note: Currently only deletes from completed queue.
    Active tasks (pending/processing) cannot be deleted.

    Args:
        task_id: Task ID to delete

    Returns:
        Status message
    """
    if _task_queue is None:
        raise HTTPException(status_code=503, detail="Task queue not initialized")

    # For now, only allow deleting completed/failed tasks
    task = await _task_queue.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    if task.status in [TaskStatus.PENDING, TaskStatus.PROCESSING]:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete active tasks. Cancel processing first."
        )

    # Remove from completed queue
    await _task_queue.remove_completed(task_id)
    logger.info(f"Task {task_id} deleted")

    return {"status": "success", "message": f"Task {task_id} deleted"}


@router.get("/stats/summary")
async def get_task_summary() -> dict:
    """Get task statistics summary.

    Returns:
        Task counts by status
    """
    if _task_queue is None:
        raise HTTPException(status_code=503, detail="Task queue not initialized")

    pending = await _task_queue.list_pending()
    processing = await _task_queue.list_processing()
    completed = await _task_queue.list_completed(limit=1000)

    # Count by status
    status_counts = {}
    type_counts = {}

    all_tasks = list(pending) + list(processing) + list(completed)
    for task in all_tasks:
        status_counts[task.status.value] = status_counts.get(task.status.value, 0) + 1
        type_counts[task.type.value] = type_counts.get(task.type.value, 0) + 1

    return {
        "total": len(all_tasks),
        "by_status": status_counts,
        "by_type": type_counts,
    }


@router.get("/templates")
async def list_templates(category: Optional[str] = None) -> dict:
    """Get list of available task templates.

    Args:
        category: Optional category filter (cron/file/email/news/organization)

    Returns:
        List of templates with metadata
    """
    from ..runner.task_templates import (
        get_template_list_for_api,
        get_templates_by_category,
        TemplateCategory,
    )

    if category:
        try:
            cat = TemplateCategory(category)
            templates = get_templates_by_category(cat)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid category: {category}")
    else:
        templates = get_template_list_for_api()

    return {"templates": templates}


class CreateTaskFromTemplateRequest(BaseModel):
    """Request body for creating a task from template."""
    template_id: str
    user_id: str
    channel: str = "console"
    session_id: str
    placeholder_values: dict = Field(
        default_factory=dict,
        description="Placeholder values for the template"
    )


@router.post("/from-template", response_model=TaskSpec)
async def create_task_from_template(request: CreateTaskFromTemplateRequest) -> TaskSpec:
    """Create a new task from a template.

    Args:
        request: Task template request with placeholder values

    Returns:
        Created task specification
    """
    from ..runner.task_templates import (
        get_template_by_id,
        build_query_from_template,
    )

    if _task_queue is None:
        raise HTTPException(status_code=503, detail="Task queue not initialized")

    # Get template
    template = get_template_by_id(request.template_id)
    if template is None:
        raise HTTPException(
            status_code=404,
            detail=f"Template {request.template_id} not found"
        )

    # Build query from template
    query = build_query_from_template(template, request.placeholder_values)

    # Create task
    task = TaskSpec(
        user_id=request.user_id,
        channel=request.channel,
        session_id=request.session_id,
        type=TaskType.INSTRUCTION,
        query=query,
        status=TaskStatus.PENDING,
        metadata={
            "template_id": request.template_id,
            "template_category": template.category.value,
            **request.placeholder_values,
        },
    )

    await _task_queue.enqueue(task)
    logger.info(
        f"Task created from template: {task.id} "
        f"(template={request.template_id})"
    )

    return task
