# -*- coding: utf-8 -*-
"""Task models for CoPaw task management.

This module defines data models for task specification and lifecycle management.
"""
from enum import Enum
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from uuid import uuid4


class TaskType(str, Enum):
    """Task type.

    Defines the type of task:
    - INSTRUCTION: Execute an action (create cron, write file, etc.)
    - RULE: Save a rule to memory
    - CONVERSATION: Normal conversation
    """
    INSTRUCTION = "instruction"
    RULE = "rule"
    CONVERSATION = "conversation"


class TaskStatus(str, Enum):
    """Task status.

    Lifecycle:
    PENDING -> PROCESSING -> WAITING_VERIFICATION -> COMPLETED
                                |-> FAILED -> REPROCESSING -> ...
    """
    PENDING = "pending"
    PROCESSING = "processing"
    WAITING_VERIFICATION = "waiting_verification"
    COMPLETED = "completed"
    FAILED = "failed"
    REPROCESSING = "reprocessing"


class TaskSpec(BaseModel):
    """Task specification.

    Attributes:
        id: Unique task identifier
        user_id: User who created the task
        channel: Channel where the task originated
        session_id: Session ID for the task
        type: Task type (instruction/rule/conversation)
        query: Original user query
        status: Current task status
        created_at: Task creation timestamp
        started_at: Task processing start timestamp
        completed_at: Task completion timestamp
        llm_response: LLM response content
        verification_result: Whether verification passed
        verification_details: Verification error details
        retry_count: Number of retry attempts
        max_retries: Maximum retry attempts allowed
        last_error: Last error message
        metadata: Additional task metadata
    """
    id: str = Field(default_factory=lambda: str(uuid4()))

    # Context
    user_id: str
    channel: str
    session_id: str

    # Task content
    type: TaskType
    query: str

    # Status tracking
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Results
    llm_response: Optional[str] = None
    verification_result: Optional[bool] = None
    verification_details: Optional[str] = None

    # Retry info
    retry_count: int = 0
    max_retries: int = 3
    last_error: Optional[str] = None

    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        """Pydantic model config."""
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            TaskType: lambda v: v.value,
            TaskStatus: lambda v: v.value,
        }

    def is_terminal(self) -> bool:
        """Check if task is in terminal state."""
        return self.status in (TaskStatus.COMPLETED, TaskStatus.FAILED)

    def can_retry(self) -> bool:
        """Check if task can be retried."""
        return (
            self.status == TaskStatus.FAILED and
            self.retry_count < self.max_retries
        )


__all__ = ["TaskType", "TaskStatus", "TaskSpec"]
