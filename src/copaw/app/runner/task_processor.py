# -*- coding: utf-8 -*-
"""Task Processor for CoPaw.

This module provides task classification and processing capabilities,
handling instructions, rules, and conversations with verification.

Features:
- Message type classification (instruction/rule/conversation)
- Instruction execution with result verification
- Rule extraction and persistence
- Auto-retry on failure

Example:
    >>> from copaw.app.runner.task_processor import TaskProcessor
    >>> processor = TaskProcessor(task_queue, rule_manager, persona_manager)
    >>> await processor.start()
    >>> await processor.process_task(task)
"""
import asyncio
import logging
import re
from typing import Optional, Tuple, List

from .task_models import TaskSpec, TaskType, TaskStatus
from .task_queue import TaskQueue

logger = logging.getLogger(__name__)

__all__ = ["TaskProcessor", "TaskClassifier"]


class TaskClassifier:
    """Classify task type based on query content.

    Uses keyword matching and optional LLM-based classification.
    """

    # Keywords that indicate an instruction
    INSTRUCTION_KEYWORDS = [
        # Chinese
        "创建", "删除", "修改", "设置", "启动", "停止", "执行", "运行",
        "添加", "移除", "更新", "打开", "关闭", "保存", "发送",
        # English
        "create", "delete", "modify", "set", "start", "stop", "execute",
        "run", "add", "remove", "update", "open", "close", "save", "send",
    ]

    # Keywords that indicate a rule
    RULE_KEYWORDS = [
        # Chinese
        "记住", "总是", "必须", "不要", "禁止", "一定", "务必", "记得",
        "以后都", "每次都", "永远", "所有", "任何",
        # English
        "remember", "always", "must", "never", "don't", "do not",
        "every time", "whenever", "make sure", "ensure",
    ]

    # Patterns for rule extraction
    RULE_PATTERNS = [
        r"[记住记得] [，,.]*(.+)",  # "记住，..."
        r"[总是必须一定务必]([，,.]*.+)?",  # "总是..."
        r"[不要禁止别]([，,.]*.+)?",  # "不要..."
        r"remember[,. ]*(.+)",  # "remember, ..."
        r"always[,. ]*(.+)",  # "always ..."
        r"never[,. ]*(.+)",  # "never ..."
    ]

    @classmethod
    def classify(cls, query: str) -> TaskType:
        """Classify a query into task type.

        Args:
            query: User query string

        Returns:
            TaskType (INSTRUCTION, RULE, or CONVERSATION)
        """
        query_lower = query.lower()

        # Check for rule keywords first (higher priority)
        for keyword in cls.RULE_KEYWORDS:
            if keyword in query_lower:
                return TaskType.RULE

        # Check for instruction keywords
        for keyword in cls.INSTRUCTION_KEYWORDS:
            if keyword in query_lower:
                return TaskType.INSTRUCTION

        # Default to conversation
        return TaskType.CONVERSATION

    @classmethod
    def extract_rule_content(cls, query: str) -> Optional[str]:
        """Extract rule content from a query.

        Args:
            query: User query that may contain a rule

        Returns:
            Extracted rule content, or None if no rule found
        """
        for pattern in cls.RULE_PATTERNS:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                content = match.group(1).strip() if match.lastindex else match.group(0).strip()
                # Clean up common prefixes
                content = re.sub(r"^[，,. ]+", "", content)
                if content:
                    return content

        # If no pattern matched, return the original query as rule
        return query.strip() if query.strip() else None


class TaskProcessor:
    """Task processor with verification and retry support.

    This processor handles:
    - Task classification
    - Instruction execution with verification
    - Rule extraction and persistence
    - Conversation passthrough
    - Auto-retry on failure

    Attributes:
        task_queue: TaskQueue instance
        rule_manager: RuleManager instance (optional)
        persona_manager: PersonaManager instance (optional)
        agent: Agent instance for LLM calls (optional)
    """

    def __init__(
        self,
        task_queue: TaskQueue,
        rule_manager=None,
        persona_manager=None,
        agent=None,
    ):
        """Initialize TaskProcessor.

        Args:
            task_queue: TaskQueue for task management
            rule_manager: RuleManager for rule persistence (optional)
            persona_manager: PersonaManager for persona management (optional)
            agent: Agent for LLM-based classification (optional)
        """
        self.task_queue = task_queue
        self.rule_manager = rule_manager
        self.persona_manager = persona_manager
        self.agent = agent
        self._running = False
        self._worker_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Start the task processing loop."""
        self._running = True
        self._worker_task = asyncio.create_task(self._process_loop())
        logger.info("TaskProcessor started")

    async def stop(self) -> None:
        """Stop the task processing loop."""
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        logger.info("TaskProcessor stopped")

    async def _process_loop(self) -> None:
        """Main processing loop."""
        while self._running:
            task = await self.task_queue.dequeue()
            if task:
                try:
                    await self.process_task(task)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.exception(f"Error processing task {task.id}: {e}")
                    await self.task_queue.fail(task.id, str(e))
            else:
                await asyncio.sleep(0.1)  # Avoid busy-waiting

    async def process_task(self, task: TaskSpec) -> None:
        """Process a single task.

        Args:
            task: TaskSpec to process
        """
        logger.info(f"Processing task {task.id}: {task.query[:50]}...")

        # Classify task type if not already classified
        if task.type is None:
            task.type = TaskClassifier.classify(task.query)
            logger.debug(f"Task {task.id} classified as {task.type}")

        # Route to appropriate handler
        if task.type == TaskType.INSTRUCTION:
            await self._handle_instruction(task)
        elif task.type == TaskType.RULE:
            await self._handle_rule(task)
        else:  # CONVERSATION
            await self._handle_conversation(task)

    async def _handle_instruction(self, task: TaskSpec) -> None:
        """Handle an instruction task.

        Flow:
        1. Execute instruction (via agent or direct)
        2. Verify result
        3. Retry if failed

        Args:
            task: Instruction task to handle
        """
        # For now, we just mark it as completed
        # In real implementation, this would call the agent
        logger.info(f"Handling instruction: {task.query}")

        # Placeholder - actual implementation would call agent
        response = f"Instruction executed: {task.query}"

        # Verify the result
        verified, details = await self._verify_instruction(task, response)

        if verified:
            await self.task_queue.complete(task.id, response)
            logger.info(f"Task {task.id} completed successfully")
        else:
            # Retry if possible
            if task.can_retry():
                logger.warning(f"Task {task.id} verification failed, retrying: {details}")
                task.status = TaskStatus.PENDING
                task.last_error = details
                await self.task_queue.enqueue(task)
            else:
                await self.task_queue.fail(task.id, f"Verification failed: {details}")

    async def _handle_rule(self, task: TaskSpec) -> None:
        """Handle a rule task.

        Flow:
        1. Extract rule content
        2. Save to RuleManager
        3. Confirm to user

        Args:
            task: Rule task to handle
        """
        logger.info(f"Handling rule: {task.query}")

        if not self.rule_manager:
            # No rule manager, treat as conversation
            response = f"Rule noted (but not saved): {task.query}"
            await self.task_queue.complete(task.id, response)
            return

        # Extract rule content
        rule_content = TaskClassifier.extract_rule_content(task.query)
        if not rule_content:
            await self.task_queue.fail(task.id, "Could not extract rule content")
            return

        # Determine rule scope based on task context
        from ..agents.rules import RuleScope
        scope = RuleScope.GLOBAL
        if task.channel:
            scope = RuleScope.CHANNEL
        if task.user_id:
            scope = RuleScope.USER

        try:
            # Save rule
            await self.rule_manager.add_rule(
                content=rule_content,
                scope=scope,
                channel=task.channel if scope == RuleScope.CHANNEL else None,
                user_id=task.user_id if scope == RuleScope.USER else None,
                priority=10,  # Default high priority for user-defined rules
            )
            response = f"规则已保存：{rule_content}"
            await self.task_queue.complete(task.id, response)
            logger.info(f"Rule saved: {rule_content}")
        except Exception as e:
            await self.task_queue.fail(task.id, f"Failed to save rule: {e}")

    async def _handle_conversation(self, task: TaskSpec) -> None:
        """Handle a conversation task.

        Args:
            task: Conversation task to handle
        """
        logger.debug(f"Handling conversation: {task.query}")

        # For conversation, just pass through
        # Actual implementation would call the agent
        response = f"Conversation response to: {task.query}"
        await self.task_queue.complete(task.id, response)

    async def _verify_instruction(
        self,
        task: TaskSpec,
        response: str,
    ) -> Tuple[bool, str]:
        """Verify an instruction execution result.

        Args:
            task: The instruction task
            response: Agent response

        Returns:
            Tuple of (success, details)
        """
        query_lower = task.query.lower()

        # Check for cron/task related keywords
        if any(kw in query_lower for kw in ["cron", "定时", "任务", "job"]):
            return await self._verify_cron_task(response)

        # Check for file operations
        if any(kw in query_lower for kw in ["file", "文件", "write", "read", "save"]):
            return await self._verify_file_operation(task.query, response)

        # Default: assume success
        return True, ""

    async def _verify_cron_task(self, response: str) -> Tuple[bool, str]:
        """Verify a cron task creation.

        Args:
            response: Agent response

        Returns:
            Tuple of (success, details)
        """
        # Check for success indicators
        success_indicators = [
            "job_id", "job created", "任务创建", "定时任务",
            "scheduled", "created successfully",
        ]
        response_lower = response.lower()

        for indicator in success_indicators:
            if indicator.lower() in response_lower:
                return True, ""

        return False, "Response does not indicate successful cron creation"

    async def _verify_file_operation(
        self,
        query: str,
        response: str,
    ) -> Tuple[bool, str]:
        """Verify a file operation.

        Args:
            query: Original query
            response: Agent response

        Returns:
            Tuple of (success, details)
        """
        # Check for success indicators
        success_indicators = [
            "success", "完成", "成功", "saved", "created", "written",
            "文件已", "已保存",
        ]
        response_lower = response.lower()

        for indicator in success_indicators:
            if indicator.lower() in response_lower:
                return True, ""

        return False, "Response does not indicate successful file operation"

    async def reprocess_failed_task(self, task: TaskSpec) -> None:
        """Reprocess a failed task.

        Args:
            task: Failed task to reprocess
        """
        if not task.can_retry():
            logger.warning(f"Task {task.id} cannot be retried (max retries reached)")
            return

        task.status = TaskStatus.REPROCESSING
        task.retry_count += 1
        await self.task_queue.enqueue(task)
        logger.info(f"Task {task.id} requeued for reprocessing (attempt {task.retry_count})")
