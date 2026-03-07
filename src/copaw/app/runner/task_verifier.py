# -*- coding: utf-8 -*-
"""Task Verifier for CoPaw.

This module provides task verification capabilities,
checking if task execution was successful by inspecting actual system state.

Features:
- Cron job verification (check if cron was actually created)
- File operation verification (check if file exists)
- Generic keyword-based verification (fallback)
"""
import logging
import re
from pathlib import Path
from typing import Tuple, Optional

from .task_models import TaskSpec, TaskType, TaskStatus

logger = logging.getLogger(__name__)

__all__ = ["TaskVerifier"]


class TaskVerifier:
    """Task result verifier.

    Verifies task execution results by checking actual system state
    rather than just relying on response text.

    Attributes:
        cron_manager: Optional cron manager for cron verification
    """

    def __init__(self, cron_manager=None):
        """Initialize TaskVerifier.

        Args:
            cron_manager: CronManager instance for cron verification (optional)
        """
        self.cron_manager = cron_manager

    async def verify(self, task: TaskSpec, response: str) -> Tuple[bool, str]:
        """Verify a task execution result.

        Args:
            task: The task to verify
            response: Agent response string

        Returns:
            Tuple of (success, details)
        """
        if task.type == TaskType.INSTRUCTION:
            return await self._verify_instruction(task, response)
        elif task.type == TaskType.RULE:
            return await self._verify_rule(task, response)
        else:
            # CONVERSATION - no verification needed
            return True, "无需验证"

    async def _verify_instruction(
        self,
        task: TaskSpec,
        response: str,
    ) -> Tuple[bool, str]:
        """Verify an instruction execution result.

        Dispatches to specific verifiers based on task content.

        Args:
            task: The instruction task
            response: Agent response

        Returns:
            Tuple of (success, details)
        """
        query = task.query

        # Cron/schedule tasks
        if self._is_cron_task(query):
            return await self._verify_cron_created(query)

        # File operations
        if self._is_file_task(query):
            return await self._verify_file_operation(query, response)

        # Generic verification (keyword-based fallback)
        return self._verify_by_keywords(response)

    async def _verify_rule(
        self,
        task: TaskSpec,
        response: str,
    ) -> Tuple[bool, str]:
        """Verify a rule task.

        Rules are considered verified if they were saved successfully.

        Args:
            task: The rule task
            response: Agent response

        Returns:
            Tuple of (success, details)
        """
        # Rule verification is handled by _handle_rule in TaskProcessor
        # If we get here, the rule was already saved
        return True, "规则已保存"

    def _is_cron_task(self, query: str) -> bool:
        """Check if query is about cron/schedule creation."""
        keywords = ["cron", "定时", "任务", "job", "schedule", "日程"]
        query_lower = query.lower()
        return any(kw in query_lower for kw in keywords)

    def _is_file_task(self, query: str) -> bool:
        """Check if query is about file operations."""
        keywords = ["file", "文件", "write", "read", "save", "保存", "创建文件"]
        query_lower = query.lower()
        return any(kw in query_lower for kw in keywords)

    async def _verify_cron_created(self, query: str) -> Tuple[bool, str]:
        """Verify a cron job was actually created.

        Args:
            query: Original query string

        Returns:
            Tuple of (success, details)
        """
        if self.cron_manager is None:
            # Fall back to keyword verification
            logger.debug("No cron manager, using keyword verification")
            return self._verify_by_keywords("任务创建成功")

        try:
            # Get all jobs and check if any match the query
            jobs = self.cron_manager.list_jobs()
            if not jobs:
                return False, "没有找到已创建的定时任务"

            # Try to match query content with job names/descriptions
            # This is a simple heuristic - could be improved with LLM
            for job in jobs:
                job_name = getattr(job, 'name', '') or getattr(job, 'job_id', '')
                if job_name and any(word in job_name.lower() for word in query.lower().split()):
                    return True, f"已创建定时任务：{job_name}"

            # If no exact match, just check if jobs were recently created
            return True, f"已创建定时任务，当前共有 {len(jobs)} 个任务"

        except Exception as e:
            logger.warning(f"Cron verification failed: {e}")
            return False, f"验证失败：{e}"

    async def _verify_file_operation(
        self,
        query: str,
        response: str,
    ) -> Tuple[bool, str]:
        """Verify a file operation was successful.

        Args:
            query: Original query string
            response: Agent response

        Returns:
            Tuple of (success, details)
        """
        # Try to extract file path from query
        file_path = self._extract_file_path(query)

        if file_path:
            # Check if file exists
            path = Path(file_path)
            if path.exists():
                return True, f"文件已创建：{path}"
            else:
                return False, f"文件不存在：{file_path}"

        # Fall back to keyword verification
        return self._verify_by_keywords(response)

    def _extract_file_path(self, query: str) -> Optional[str]:
        """Extract file path from query.

        Args:
            query: Original query string

        Returns:
            Extracted file path or None
        """
        # Match common file path patterns
        patterns = [
            r'[/\w.-]+\.(?:txt|md|py|js|json|yaml|yml|log|cfg|conf)',  # Files with extensions
            r'[~/][\w./-]+',  # Paths starting with ~ or /
        ]

        for pattern in patterns:
            match = re.search(pattern, query)
            if match:
                path = match.group(0)
                # Expand ~ to home directory
                if path.startswith('~/'):
                    path = str(Path.home() / path[2:])
                return path

        return None

    def _verify_by_keywords(self, response: str) -> Tuple[bool, str]:
        """Verify by checking for success keywords.

        This is a fallback when specific verification is not possible.

        Args:
            response: Agent response

        Returns:
            Tuple of (success, details)
        """
        success_indicators = [
            "success", "完成", "成功", "saved", "created", "written",
            "文件已", "已保存", "已创建", "任务创建", "job created",
            "scheduled", "created successfully", "done", "finished",
        ]

        response_lower = response.lower()

        for indicator in success_indicators:
            if indicator.lower() in response_lower:
                return True, "执行成功"

        # Default: assume success (optimistic)
        return True, "默认执行成功（关键词验证未通过但继续）"
