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
from datetime import datetime, timezone
from typing import Optional, Tuple, List

from .task_models import TaskSpec, TaskType, TaskStatus
from .task_queue import TaskQueue
from .task_verifier import TaskVerifier

logger = logging.getLogger(__name__)

__all__ = ["TaskProcessor", "TaskClassifier", "broadcast_progress"]

# Maximum time to wait for agent to become available (in seconds)
AGENT_WAIT_TIMEOUT = 60.0
# Check interval for agent availability (in seconds)
AGENT_WAIT_INTERVAL = 1.0

# Global broadcaster reference (set by app initialization)
_progress_broadcaster = None


def set_progress_broadcaster(broadcaster) -> None:
    """Set progress broadcaster for task processor."""
    global _progress_broadcaster
    _progress_broadcaster = broadcaster


def broadcast_progress(task_id: str, event_type: str, **data) -> None:
    """Broadcast progress event to WebSocket clients.

    Args:
        task_id: Task UUID
        event_type: Event type (status/thought/tool/result/progress)
        **data: Event data fields
    """
    if _progress_broadcaster is None:
        return
    # Schedule broadcast without blocking
    asyncio.create_task(_progress_broadcaster.broadcast(task_id, {
        "type": event_type,
        **data,
    }))


class TaskClassifier:
    """Classify task type based on query content.

    Uses keyword matching and optional LLM-based classification.
    """

    # Keywords that indicate an instruction
    INSTRUCTION_KEYWORDS = [
        # Chinese
        "创建", "删除", "修改", "设置", "启动", "停止", "执行", "运行",
        "添加", "移除", "更新", "打开", "关闭", "保存", "发送",
        # Analysis/Stock related
        "分析", "评估", "研究", "调查", "查询", "获取", "检查", "查看",
        # English
        "create", "delete", "modify", "set", "start", "stop", "execute",
        "run", "add", "remove", "update", "open", "close", "save", "send",
        # Analysis/Stock related
        "analyze", "evaluate", "research", "investigate", "check", "get",
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
        cron_manager: CronManager instance (optional)
        agent_instance_manager: AgentInstanceManager instance (optional)
    """

    def __init__(
        self,
        task_queue: TaskQueue,
        rule_manager=None,
        persona_manager=None,
        cron_manager=None,
        agent_instance_manager=None,
        chat_manager=None,
    ):
        """Initialize TaskProcessor.

        Args:
            task_queue: TaskQueue for task management
            rule_manager: RuleManager for rule persistence (optional)
            persona_manager: PersonaManager for persona management (optional)
            cron_manager: CronManager for cron verification (optional)
            agent_instance_manager: AgentInstanceManager for multi-agent routing (optional)
            chat_manager: ChatManager for chat metadata updates (optional)
        """
        self.task_queue = task_queue
        self.rule_manager = rule_manager
        self.persona_manager = persona_manager
        # Note: We don't store agent as a property - each task creates its own agent
        # to avoid conflicts with real-time requests (agent instances are not thread-safe)
        self.cron_manager = cron_manager
        self.agent_instance_manager = agent_instance_manager
        self.chat_manager = chat_manager  # For updating chat metadata
        self._running = False
        self._worker_task: Optional[asyncio.Task] = None

        # Initialize verifier
        self.verifier = TaskVerifier(cron_manager=cron_manager)

    async def _get_or_create_agent(self, channel: str, user_id: str, session_id: str):
        """Create a new agent for task processing.

        Note: We create a new agent for each task to avoid conflicts with
        the agent used by real-time requests. Agent instances are not thread-safe.

        Args:
            channel: Channel identifier
            user_id: User identifier
            session_id: Session identifier

        Returns:
            CoPawAgent instance
        """
        logger.info(f"Creating agent for task processing (channel={channel}, user_id={user_id})")

        try:
            from agentscope.message import Msg
            from copaw.agents.react_agent import CoPawAgent
            from copaw.app.runner.utils import build_env_context
            from copaw.config import load_config
            from copaw.constant import WORKING_DIR

            # Build environment context
            env_context = build_env_context(
                session_id=session_id,
                user_id=user_id,
                channel=channel,
                working_dir=str(WORKING_DIR),
            )

            # Load config
            config = load_config()
            max_iters = config.agents.running.max_iters
            max_input_length = config.agents.running.max_input_length

            # Get MCP clients from manager if available
            mcp_clients = []
            # Note: MCP manager is not directly accessible here, skip for now
            # MCP clients will be registered via agent.register_mcp_clients()

            # Create a NEW agent for each task (don't reuse self.agent to avoid conflicts)
            agent = CoPawAgent(
                env_context=env_context,
                mcp_clients=mcp_clients,
                memory_manager=None,  # Task processing doesn't need persistent memory
                max_iters=max_iters,
                max_input_length=max_input_length,
                rule_manager=self.rule_manager,
                persona_manager=self.persona_manager,
                channel=channel,
                user_id=user_id,
                session_id=session_id,
                agent_instance_manager=self.agent_instance_manager,
            )

            # Register MCP clients if available
            await agent.register_mcp_clients()

            # Don't set as self.agent - each task gets its own agent
            # This avoids conflicts with real-time requests
            logger.info("Agent created for task processing")

            return agent

        except Exception as e:
            logger.exception(f"Failed to create agent for task: {e}")
            raise

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
        logger.info("TaskProcessor _process_loop started")
        while self._running:
            task = await self.task_queue.dequeue()
            if task:
                logger.info(f"TaskProcessor dequeued task {task.id}")
                try:
                    await self.process_task(task)
                except asyncio.CancelledError as e:
                    # Task was re-queued due to agent unavailability or max retries reached
                    # Check if task was re-queued or should be failed
                    if task.retry_count < task.max_retries:
                        logger.debug(f"Task {task.id} re-queued, skipping error handling")
                    else:
                        # Max retries reached, mark task as failed
                        logger.error(f"Task {task.id} failed: {e}")
                        await self.task_queue.fail(task.id, str(e))
                    continue
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
        1. Task is executed in real-time chat by runner
        2. TaskProcessor verifies the result after completion
        3. Retry if verification failed

        Args:
            task: Instruction task to handle
        """
        logger.info(f"Handling instruction: {task.query}")

        # Task should already be completed by runner in real-time chat
        # We only need to verify the result
        if task.status != TaskStatus.COMPLETED or not task.llm_response:
            # Task not completed yet - this shouldn't happen in normal flow
            # Wait for runner to complete it first
            logger.info(f"Task {task.id}: Not completed yet, waiting for runner...")
            # Re-enqueue with delay to let runner complete it
            await asyncio.sleep(0.5)  # Give runner time to complete
            # Refresh task status from queue
            fresh_task = await self.task_queue.get_task(task.id)
            if fresh_task:
                task = fresh_task

        # Now verify the result
        if task.status == TaskStatus.COMPLETED and task.llm_response:
            response = task.llm_response
            logger.info(f"Task {task.id}: Completed in chat, verifying result...")

            # Broadcast existing result for WebSocket UI updates
            broadcast_progress(task.id, "result", response=response)
        else:
            # Still not completed - something went wrong
            logger.warning(f"Task {task.id}: Still not completed after waiting, skipping verification")
            return

        logger.info(f"Task {task.id}: Verifying result...")

        # Verify the result using TaskVerifier
        verified, details = await self.verifier.verify(task, response)
        logger.info(f"Task {task.id}: Verification result: verified={verified}, details={details}")

        if verified:
            logger.info(f"Task {task.id}: Completing task...")
            await self.task_queue.complete(task.id, response)
            logger.info(f"Task {task.id}: Task completed in queue, marking as verified...")
            await self.task_queue.mark_verified(task.id, True, details)
            broadcast_progress(task.id, "status", status="completed", verified=True)

            # Update chat metadata with last message
            if self.chat_manager is not None:
                try:
                    chat = await self.chat_manager.get_or_create_chat(
                        task.session_id or "default",
                        task.user_id or "default",
                        task.channel or "console",
                    )
                    chat.meta["last_message"] = response[:200] if response else ""
                    chat.meta["last_message_at"] = datetime.now(timezone.utc).isoformat()
                    chat.updated_at = datetime.now(timezone.utc)
                    await self.chat_manager.update_chat(chat)
                    logger.info(f"Task {task.id}: Chat metadata updated")
                except Exception as e:
                    logger.warning(f"Task {task.id}: Failed to update chat metadata: {e}")

            # Skip sending result to user - it was already shown in chat
            # WebSocket broadcasts are still used for task list UI updates

            logger.info(f"Task {task.id} completed and verified successfully")
        else:
            # Retry if possible
            if task.can_retry():
                logger.warning(f"Task {task.id} verification failed, retrying: {details}")
                task.status = TaskStatus.PENDING
                task.last_error = details
                broadcast_progress(task.id, "status", status="retrying", reason=details)
                await self.task_queue.enqueue(task)
            else:
                await self.task_queue.fail(task.id, f"Verification failed: {details}")
                broadcast_progress(task.id, "status", status="failed", error=details)
                logger.error(f"Task {task.id} failed after max retries: {details}")

    async def _execute_with_agent(self, task: TaskSpec) -> str:
        """Execute instruction using CoPawAgent.

        Args:
            task: The instruction task

        Returns:
            Agent response string
        """
        # Get or create agent lazily
        logger.info(f"Task {task.id}: Getting or creating agent...")
        agent = await self._get_or_create_agent(
            channel=task.channel or "console",
            user_id=task.user_id or "default",
            session_id=task.session_id or "default",
        )
        logger.info(f"Task {task.id}: Agent obtained, calling reply()...")

        try:
            from agentscope.message import Msg

            # Create user message
            user_msg = Msg(name="user", content=task.query, role="user")

            # Call agent with timeout to prevent blocking the process loop
            logger.info(f"Task {task.id}: Calling agent.reply() with timeout=300s...")
            response_msg = await asyncio.wait_for(
                agent.reply(user_msg),
                timeout=300.0  # 5 minute timeout
            )
            logger.info(f"Task {task.id}: agent.reply() returned")

            # Extract text content from response
            logger.info(f"Task {task.id}: Extracting response content...")
            if hasattr(response_msg, 'get_text_content'):
                result = response_msg.get_text_content() or str(response_msg)
            else:
                result = str(response_msg)
            logger.info(f"Task {task.id}: Response extracted: {result[:100]}...")
            return result

        except asyncio.CancelledError:
            # Re-raise without logging error (task already re-queued or max retries reached)
            logger.warning(f"Task {task.id}: Execution cancelled")
            raise
        except asyncio.TimeoutError:
            logger.error(f"Agent execution timeout for task {task.id}")
            raise TimeoutError(f"Agent execution timeout after 300s for task {task.id}")
        except Exception as e:
            logger.exception(f"Agent execution failed: {e}")
            raise

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

        For complex conversations like stock analysis, call the agent
        and record the result as a task.

        Args:
            task: Conversation task to handle
        """
        logger.info(f"Handling conversation: {task.query}")

        # Call agent for conversation
        response = await self._execute_with_agent(task)

        # Complete the task with agent response
        await self.task_queue.complete(task.id, response)
        logger.info(f"Task {task.id} completed with conversation response")

    # Note: Verification is now handled by TaskVerifier class
    # The _verify_instruction, _verify_cron_task, and _verify_file_operation
    # methods have been moved to task_verifier.py for better organization

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
