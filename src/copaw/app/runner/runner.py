# -*- coding: utf-8 -*-
# pylint: disable=unused-argument too-many-branches too-many-statements
import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from agentscope.message import Msg
from agentscope.pipeline import stream_printing_messages
from agentscope_runtime.engine.runner import Runner
from agentscope_runtime.engine.schemas.agent_schemas import AgentRequest
from dotenv import load_dotenv

from .query_error_dump import write_query_error_dump
from .session import SafeJSONSession
from .task_models import TaskSpec, TaskType, TaskStatus
from .utils import build_env_context
from ..channels.schema import DEFAULT_CHANNEL
from ...agents.memory import MemoryManager
from ...agents.react_agent import CoPawAgent
from ...config import load_config
from ...constant import WORKING_DIR

logger = logging.getLogger(__name__)


class AgentRunner(Runner):
    def __init__(self) -> None:
        super().__init__()
        self.framework_type = "agentscope"
        self._chat_manager = None  # Store chat_manager reference
        self._mcp_manager = None  # MCP client manager for hot-reload

        self.memory_manager: MemoryManager | None = None

        # Enhancement: Task and rule management (PR #3, #4, #5, #6)
        self._task_queue = None
        self._task_processor = None
        self._rule_manager = None
        self._persona_manager = None

        # Multi-agent support
        self._agent_instance_manager = None
        self._agent_router = None

    def set_chat_manager(self, chat_manager):
        """Set chat manager for auto-registration.

        Args:
            chat_manager: ChatManager instance
        """
        self._chat_manager = chat_manager

    def set_mcp_manager(self, mcp_manager):
        """Set MCP client manager for hot-reload support.

        Args:
            mcp_manager: MCPClientManager instance
        """
        self._mcp_manager = mcp_manager

    # Enhancement: Setter methods for managers (PR #6)
    def set_task_queue(self, task_queue):
        """Set task queue for task management.

        Args:
            task_queue: TaskQueue instance
        """
        self._task_queue = task_queue

    def set_rule_manager(self, rule_manager):
        """Set rule manager for rule management.

        Args:
            rule_manager: RuleManager instance
        """
        self._rule_manager = rule_manager

    def set_persona_manager(self, persona_manager):
        """Set persona manager for persona management.

        Args:
            persona_manager: PersonaManager instance
        """
        self._persona_manager = persona_manager

    def set_task_processor(self, task_processor):
        """Set task processor for task processing.

        Args:
            task_processor: TaskProcessor instance
        """
        self._task_processor = task_processor

    # Multi-agent support
    def set_agent_instance_manager(self, manager):
        """Set agent instance manager for multi-agent routing.

        Args:
            manager: AgentInstanceManager instance
        """
        self._agent_instance_manager = manager

    def set_agent_router(self, router):
        """Set agent router for request routing.

        Args:
            router: AgentRouter instance
        """
        self._agent_router = router

    def set_security_guard_manager(self, manager):
        """Set security guard manager for security rules.

        Args:
            manager: SecurityGuardManager instance
        """
        self._security_guard_manager = manager

    def _create_agent(
        self,
        env_context,
        mcp_clients,
        max_iters,
        max_input_length,
        channel,
        user_id,
        session_id,
    ):
        """Create CoPawAgent instance.

        Args:
            env_context: Environment context
            mcp_clients: MCP clients list
            max_iters: Maximum iterations
            max_input_length: Maximum input length
            channel: Channel identifier
            user_id: User identifier
            session_id: Session identifier

        Returns:
            CoPawAgent instance
        """
        from ...agents.react_agent import CoPawAgent

        agent = CoPawAgent(
            env_context=env_context,
            mcp_clients=mcp_clients,
            memory_manager=self.memory_manager,
            max_iters=max_iters,
            max_input_length=max_input_length,
            # Enhancement: Pass managers to agent (PR #5, #6)
            rule_manager=self._rule_manager,
            persona_manager=self._persona_manager,
            channel=channel,
            user_id=user_id,
            session_id=session_id,
            # Multi-agent: Pass agent instance manager
            agent_instance_manager=self._agent_instance_manager,
            # Security guard: Pass security guard manager
            security_guard_manager=self._security_guard_manager,
        )

        return agent

    async def query_handler(
        self,
        msgs,
        request: AgentRequest = None,
        **kwargs,
    ):
        """
        Handle agent query.
        """

        agent = None
        chat = None
        chat_updated = False  # Track if chat metadata was updated

        try:
            session_id = request.session_id
            user_id = request.user_id
            channel = getattr(request, "channel", DEFAULT_CHANNEL)

            logger.info(
                "Handle agent query:\n%s",
                json.dumps(
                    {
                        "session_id": session_id,
                        "user_id": user_id,
                        "channel": channel,
                        "msgs_len": len(msgs) if msgs else 0,
                        "msgs_str": str(msgs)[:300] + "...",
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
            )

            # Extract message text for task classification
            message_text = ""
            if msgs:
                first_msg = msgs[0]
                if hasattr(first_msg, 'get_text_content'):
                    message_text = first_msg.get_text_content() or ""
                else:
                    message_text = str(first_msg)

            # Pre-load common dependencies
            env_context = build_env_context(
                session_id=session_id,
                user_id=user_id,
                channel=channel,
                working_dir=str(WORKING_DIR),
            )

            # Get MCP clients from manager (hot-reloadable)
            mcp_clients = []
            if self._mcp_manager is not None:
                mcp_clients = await self._mcp_manager.get_clients()

            config = load_config()
            max_iters = config.agents.running.max_iters
            max_input_length = config.agents.running.max_input_length

            # Task integration: Create task only for INSTRUCTION/RULE types
            task_created = False
            created_task_id = None
            task_type = None

            if message_text and self._task_queue is not None:
                from .task_processor import TaskClassifier
                task_type = TaskClassifier.classify(message_text)

                # Only create tasks for INSTRUCTION/RULE types, not CONVERSATION
                # Also skip Heartbeat tasks (user_id="main", session_id="main")
                if task_type in [TaskType.INSTRUCTION, TaskType.RULE]:
                    # Skip Heartbeat tasks - they are system tasks, not user tasks
                    is_heartbeat = (user_id == "main" and session_id == "main")
                    if not is_heartbeat:
                        task = TaskSpec(
                            user_id=user_id,
                            channel=channel,
                            session_id=session_id,
                            type=task_type,
                            query=message_text,
                            status=TaskStatus.PENDING,
                        )
                        await self._task_queue.enqueue(task)
                        task_created = True
                        created_task_id = task.id
                        logger.info(f"Task created: {task.id} (type={task_type})")
                    else:
                        logger.debug("Skipping task creation for Heartbeat query")

            # Continue to process ALL types in real-time through the agent
            # Task is only for tracking/verification, not for replacing chat
            agent = self._create_agent(
                env_context=env_context,
                mcp_clients=mcp_clients,
                max_iters=max_iters,
                max_input_length=max_input_length,
                channel=channel,
                user_id=user_id,
                session_id=session_id,
            )

            # Note: We don't set agent for task processor anymore
            # Each task creates its own agent to avoid conflicts

            await agent.register_mcp_clients()
            agent.set_console_output_enabled(enabled=False)

            logger.debug(
                f"Agent Query msgs {msgs}",
            )

            name = "New Chat"
            if len(msgs) > 0:
                content = msgs[0].get_text_content()
                if content:
                    name = msgs[0].get_text_content()[:10]
                else:
                    name = "Media Message"

            if self._chat_manager is not None:
                chat = await self._chat_manager.get_or_create_chat(
                    session_id,
                    user_id,
                    channel,
                    name=name,
                )

            await self.session.load_session_state(
                session_id=session_id,
                user_id=user_id,
                agent=agent,
            )

            # Rebuild system prompt so it always reflects the latest
            # AGENTS.md / SOUL.md / PROFILE.md, not the stale one saved
            # in the session state.
            agent.rebuild_sys_prompt()

            async for msg, last in stream_printing_messages(
                agents=[agent],
                coroutine_task=agent(msgs),
            ):
                yield msg, last

        except asyncio.CancelledError:
            if agent is not None:
                await agent.interrupt()
            raise
        except Exception as e:
            debug_dump_path = write_query_error_dump(
                request=request,
                exc=e,
                locals_=locals(),
            )
            path_hint = (
                f"\n(Details:  {debug_dump_path})" if debug_dump_path else ""
            )
            logger.exception(f"Error in query handler: {e}{path_hint}")
            if debug_dump_path:
                setattr(e, "debug_dump_path", debug_dump_path)
                if hasattr(e, "add_note"):
                    e.add_note(
                        f"(Details:  {debug_dump_path})",
                    )
                suffix = f"\n(Details:  {debug_dump_path})"
                e.args = (
                    (f"{e.args[0]}{suffix}" if e.args else suffix.strip()),
                ) + e.args[1:]
            # Mark task as failed if there was an error
            if task_created and created_task_id:
                try:
                    await self._task_queue.fail(created_task_id, str(e))
                except Exception:
                    pass
            raise
        finally:
            # Save session state for all types
            if agent is not None:
                logger.info(f"Saving session state: memory content count = {len(agent.memory.content)}")
                await self.session.save_session_state(
                    session_id=session_id,
                    user_id=user_id,
                    agent=agent,
                )

            # Update chat metadata
            if self._chat_manager is not None and chat is not None:
                await self._chat_manager.update_chat(chat)

            # Mark task as completed after chat completes
            # TaskProcessor will handle verification/retry in background
            if task_created and created_task_id:
                try:
                    # Get the last response message for the task result
                    last_response = ""
                    if chat and chat.meta:
                        last_response = chat.meta.get("last_message", "") or ""
                    # Complete the task with the response
                    await self._task_queue.complete(created_task_id, last_response)
                    logger.debug(f"Task {created_task_id} marked as completed")
                except Exception:
                    pass  # Don't fail the whole request if task update fails

    async def init_handler(self, *args, **kwargs):
        """
        Init handler.
        """
        # Load environment variables from .env file
        env_path = Path(__file__).resolve().parents[4] / ".env"
        if env_path.exists():
            load_dotenv(env_path)
            logger.debug(f"Loaded environment variables from {env_path}")
        else:
            logger.debug(
                f".env file not found at {env_path}, "
                "using existing environment variables",
            )

        session_dir = str(WORKING_DIR / "sessions")
        self.session = SafeJSONSession(save_dir=session_dir)

        try:
            if self.memory_manager is None:
                self.memory_manager = MemoryManager(
                    working_dir=str(WORKING_DIR),
                )
            await self.memory_manager.start()
        except Exception as e:
            logger.exception(f"MemoryManager start failed: {e}")

    async def shutdown_handler(self, *args, **kwargs):
        """
        Shutdown handler.
        """
        try:
            await self.memory_manager.close()
        except Exception as e:
            logger.warning(f"MemoryManager stop failed: {e}")
