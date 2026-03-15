# -*- coding: utf-8 -*-
"""CoPaw Agent - Main agent implementation.

This module provides the main CoPawAgent class built on ReActAgent,
with integrated tools, skills, and memory management.
"""
import logging
import os
from typing import Any, List, Optional, Type

from agentscope.agent import ReActAgent
from agentscope.message import Msg
from agentscope.tool import Toolkit
from pydantic import BaseModel

from .command_handler import CommandHandler
from .hooks import BootstrapHook, MemoryCompactionHook
from .memory import CoPawInMemoryMemory
from .model_factory import create_model_and_formatter
from .prompt import build_system_prompt_from_working_dir
from .skills_manager import (
    ensure_skills_initialized,
    get_working_skills_dir,
    list_available_skills,
)
from .tools import (
    browser_use,
    create_memory_search_tool,
    desktop_screenshot,
    edit_file,
    execute_shell_command,
    get_current_time,
    read_file,
    send_file_to_user,
    write_file,
)
from .skill_toolkit import register_skill_tools, set_skill_context
from .utils import process_file_and_media_blocks_in_message
from ..agents.memory import MemoryManager
from ..config import load_config
from ..constant import (
    MEMORY_COMPACT_KEEP_RECENT,
    MEMORY_COMPACT_RATIO,
    WORKING_DIR,
)

# Optional imports for enhancements (PR #1, #2, #5)
try:
    from .rules import RuleManager
except ImportError:
    RuleManager = None
try:
    from .persona import PersonaManager
except ImportError:
    PersonaManager = None
try:
    from .agent_instance import AgentInstanceManager, AgentRouter, RoutingResult
except ImportError:
    AgentInstanceManager = None
    AgentRouter = None
    RoutingResult = None
try:
    from ..security import SecurityGuardManager
except ImportError:
    SecurityGuardManager = None

logger = logging.getLogger(__name__)


class CoPawAgent(ReActAgent):
    """CoPaw Agent with integrated tools, skills, and memory management.

    This agent extends ReActAgent with:
    - Built-in tools (shell, file operations, browser, etc.)
    - Dynamic skill loading from working directory
    - Memory management with auto-compaction
    - Bootstrap guidance for first-time setup
    - System command handling (/compact, /new, etc.)
    - Rule injection for persistent constraints (enhancement)
    - Persona-based role isolation (enhancement)
    """

    def __init__(
        self,
        env_context: Optional[str] = None,
        enable_memory_manager: bool = True,
        mcp_clients: Optional[List[Any]] = None,
        memory_manager: MemoryManager | None = None,
        max_iters: int = 50,
        max_input_length: int = 128 * 1024,  # 128K = 131072 tokens
        name: str = "Friday",  # Agent name (default: "Friday")
        # Enhancement parameters (PR #5)
        rule_manager: Optional["RuleManager"] = None,
        persona_manager: Optional["PersonaManager"] = None,
        channel: Optional[str] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        # Multi-agent parameters (Phase 1)
        agent_instance_manager: Optional["AgentInstanceManager"] = None,
        is_expert_agent: bool = False,  # True if this is an expert agent (not PM)
        # Security guard parameters
        security_guard_manager: Optional["SecurityGuardManager"] = None,
    ):
        """Initialize CoPawAgent.

        Args:
            env_context: Optional environment context to prepend to
                system prompt
            enable_memory_manager: Whether to enable memory manager
            mcp_clients: Optional list of MCP clients for tool
                integration
            memory_manager: Optional memory manager instance
            max_iters: Maximum number of reasoning-acting iterations
                (default: 50)
            max_input_length: Maximum input length in tokens for model
                context window (default: 128K = 131072)
            name: Agent name (default: "Friday")
            rule_manager: Optional RuleManager for rule injection (enhancement)
            persona_manager: Optional PersonaManager for persona injection (enhancement)
            channel: Channel name for context-aware processing
            user_id: User identifier for context-aware processing
            session_id: Session identifier for context-aware processing
            agent_instance_manager: Optional AgentInstanceManager for multi-agent routing
            is_expert_agent: True if this is an expert agent (not the main PM agent)
            security_guard_manager: Optional SecurityGuardManager for security rules (enhancement)
        """
        self._env_context = env_context
        self._max_input_length = max_input_length
        self._mcp_clients = mcp_clients or []

        # Enhancement: Store context and managers (PR #5)
        self._channel = channel
        self._user_id = user_id
        self._session_id = session_id
        self._rule_manager = rule_manager
        self._persona_manager = persona_manager
        self._security_guard_manager = security_guard_manager

        # Multi-agent: Store agent instance manager (Phase 1)
        self._agent_instance_manager = agent_instance_manager
        self._agent_router: Optional["AgentRouter"] = None
        self._is_expert_agent = is_expert_agent

        # Initialize router if agent instance manager is provided
        if agent_instance_manager is not None and AgentRouter is not None:
            self._agent_router = AgentRouter(agent_instance_manager)

        # Memory compaction threshold: configurable ratio of max_input_length
        self._memory_compact_threshold = int(
            max_input_length * MEMORY_COMPACT_RATIO,
        )

        # Initialize toolkit with built-in tools
        toolkit = self._create_toolkit()

        # Load and register skills
        self._register_skills(toolkit)

        # Build system prompt
        sys_prompt = self._build_sys_prompt()

        # Create model and formatter using factory method
        model, formatter = create_model_and_formatter()

        # Initialize parent ReActAgent with the provided name
        super().__init__(
            name=name,
            model=model,
            sys_prompt=sys_prompt,
            toolkit=toolkit,
            memory=CoPawInMemoryMemory(),
            formatter=formatter,
            max_iters=max_iters,
        )

        # Setup memory manager
        self._setup_memory_manager(
            enable_memory_manager,
            memory_manager,
        )

        # Setup command handler
        self.command_handler = CommandHandler(
            agent_name=self.name,
            memory=self.memory,
            formatter=self.formatter,
            memory_manager=self.memory_manager,
            enable_memory_manager=self._enable_memory_manager,
        )

        # Register hooks
        self._register_hooks()

    def _create_toolkit(self) -> Toolkit:
        """Create and populate toolkit with built-in tools.

        Returns:
            Configured toolkit instance
        """
        toolkit = Toolkit()

        # Register built-in tools
        toolkit.register_tool_function(execute_shell_command)
        toolkit.register_tool_function(read_file)
        toolkit.register_tool_function(write_file)
        toolkit.register_tool_function(edit_file)
        toolkit.register_tool_function(browser_use)
        toolkit.register_tool_function(desktop_screenshot)
        toolkit.register_tool_function(send_file_to_user)
        toolkit.register_tool_function(get_current_time)

        return toolkit

    def _register_skills(self, toolkit: Toolkit) -> None:
        """Load and register skills from working directory.

        This method does two things:
        1. Register skill descriptions (SKILL.md) via register_agent_skill()
        2. Register Python functions from skill __init__.py as tool functions

        Args:
            toolkit: Toolkit to register skills to
        """
        # Check skills initialization
        ensure_skills_initialized()

        working_skills_dir = get_working_skills_dir()
        available_skills = list_available_skills()

        for skill_name in available_skills:
            skill_dir = working_skills_dir / skill_name
            if skill_dir.exists():
                try:
                    # Register skill description (SKILL.md)
                    toolkit.register_agent_skill(str(skill_dir))
                    logger.debug("Registered skill: %s", skill_name)
                except ValueError as e:
                    # Skill already registered (normal in multi-agent scenarios)
                    logger.debug("Skill already registered: %s - %s", skill_name, e)
                except Exception as e:
                    logger.error(
                        "Failed to register skill '%s': %s",
                        skill_name,
                        e,
                    )

        # Auto-register Python functions from all skills as tool functions
        # This enables agents to actually call the skill functions
        registered_count = register_skill_tools(toolkit, working_skills_dir)
        logger.info(f"Registered {registered_count} skill tool function(s)")

    def _build_sys_prompt(self) -> str:
        """Build system prompt from working dir files and env context.

        Returns:
            Complete system prompt string with rules and persona injected
        """
        import asyncio

        sys_prompt = build_system_prompt_from_working_dir()

        # Enhancement: Inject persona (PR #2, #5)
        if self._persona_manager:
            try:
                # Try to get persona using asyncio.run or existing loop
                persona = self._run_async(
                    self._persona_manager.get_active_persona(
                        channel=self._channel,
                        user_id=self._user_id,
                    )
                )
                if persona:
                    persona_section = (
                        f"\n\n# 当前角色：{persona.name}\n"
                        f"{persona.description}\n\n"
                        f"{persona.system_prompt_addon}"
                    )
                    sys_prompt += persona_section
                    logger.debug(f"Injected persona: {persona.name}")
            except Exception as e:
                logger.warning(f"Failed to inject persona: {e}")

        # Enhancement: Inject rules (PR #1, #5)
        if self._rule_manager:
            try:
                rules = self._run_async(
                    self._rule_manager.get_active_rules(
                        channel=self._channel,
                        user_id=self._user_id,
                        session_id=self._session_id,
                    )
                )
                if rules:
                    rules_section = "\n\n# 当前适用的规则约束\n"
                    for i, rule in enumerate(rules, 1):
                        rules_section += f"\n{i}. {rule.content}\n"
                    sys_prompt += rules_section
                    logger.debug(f"Injected {len(rules)} rules")
            except Exception as e:
                logger.warning(f"Failed to inject rules: {e}")

        # Enhancement: Inject security guard rules
        if self._security_guard_manager:
            try:
                security_rules = self._security_guard_manager.get_rules_text()
                if security_rules:
                    sys_prompt += security_rules
                    logger.debug("Injected security guard rules")
            except Exception as e:
                logger.warning(f"Failed to inject security guard rules: {e}")

        # Add environment context
        if self._env_context is not None:
            sys_prompt = self._env_context + "\n\n" + sys_prompt

        return sys_prompt

    def _run_async(self, coro):
        """Run async coroutine in sync context.

        Args:
            coro: Async coroutine to run

        Returns:
            Result of the coroutine
        """
        import asyncio
        try:
            # Try to run in current event loop context
            loop = asyncio.get_running_loop()
            # If we're in a running loop, we need to run it differently
            # This is a fallback for when called from async context
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(asyncio.run, coro)
                return future.result()
        except RuntimeError:
            # No running loop, use asyncio.run directly
            return asyncio.run(coro)

    def _setup_memory_manager(
        self,
        enable_memory_manager: bool,
        memory_manager: MemoryManager | None,
    ) -> None:
        """Setup memory manager and register memory search tool if enabled.

        Args:
            enable_memory_manager: Whether to enable memory manager
            memory_manager: Optional memory manager instance
        """
        # Check env var: if ENABLE_MEMORY_MANAGER=false, disable memory manager
        env_enable_mm = os.getenv("ENABLE_MEMORY_MANAGER", "")
        if env_enable_mm.lower() == "false":
            enable_memory_manager = False

        self._enable_memory_manager: bool = enable_memory_manager
        self.memory_manager = memory_manager

        # Register memory_search tool if enabled and available
        if self._enable_memory_manager and self.memory_manager is not None:
            self.memory_manager.chat_model = self.model
            self.memory_manager.formatter = self.formatter

            memory_search_tool = create_memory_search_tool(self.memory_manager)
            self.toolkit.register_tool_function(memory_search_tool)
            logger.debug("Registered memory_search tool")

    def _register_hooks(self) -> None:
        """Register pre-reasoning hooks for bootstrap and memory compaction."""
        # Bootstrap hook - checks BOOTSTRAP.md on first interaction
        config = load_config()
        bootstrap_hook = BootstrapHook(
            working_dir=WORKING_DIR,
            language=config.agents.language,
        )
        self.register_instance_hook(
            hook_type="pre_reasoning",
            hook_name="bootstrap_hook",
            hook=bootstrap_hook.__call__,
        )
        logger.debug("Registered bootstrap hook")

        # Memory compaction hook - auto-compact when context is full
        if self._enable_memory_manager and self.memory_manager is not None:
            memory_compact_hook = MemoryCompactionHook(
                memory_manager=self.memory_manager,
                memory_compact_threshold=self._memory_compact_threshold,
                keep_recent=MEMORY_COMPACT_KEEP_RECENT,
            )
            self.register_instance_hook(
                hook_type="pre_reasoning",
                hook_name="memory_compact_hook",
                hook=memory_compact_hook.__call__,
            )
            logger.debug("Registered memory compaction hook")

    def rebuild_sys_prompt(self) -> None:
        """Rebuild and replace the system prompt.

        Useful after load_session_state to ensure the prompt reflects
        the latest AGENTS.md / SOUL.md / PROFILE.md on disk.

        Updates both self._sys_prompt and the first system-role
        message stored in self.memory.content (if one exists).
        """
        self._sys_prompt = self._build_sys_prompt()

        for msg, _marks in self.memory.content:
            if msg.role == "system":
                msg.content = self.sys_prompt
            break

    async def register_mcp_clients(self) -> None:
        """Register MCP clients on this agent's toolkit after construction."""
        for client in self._mcp_clients:
            await self.toolkit.register_mcp_client(client)

    async def reply(
        self,
        msg: Msg | list[Msg] | None = None,
        structured_model: Type[BaseModel] | None = None,
    ) -> Msg:
        """Override reply to process file blocks, handle commands, and route messages.

        For the main PM agent (is_expert_agent=False):
        1. Check if message should be routed to an expert agent
        2. If routed, delegate to the expert agent
        3. Otherwise, process normally

        For expert agents (is_expert_agent=True):
        - Process messages directly without routing

        Args:
            msg: Input message(s) from user
            structured_model: Optional pydantic model for structured output

        Returns:
            Response message
        """
        # Set skill context before processing so skill functions can access
        # current channel/user/session (e.g., for cron job creation)
        set_skill_context(
            channel=self._channel,
            user_id=self._user_id,
            session_id=self._session_id,
        )
        logger.debug(
            f"[Skill Context] 设置 context: channel={self._channel}, "
            f"user_id={(self._user_id or '')[:20]}, session_id={(self._session_id or '')[:20]}"
        )

        # Log agent identity at the start of message processing
        logger.info(
            f"[Agent 处理] 开始处理消息 - Agent: {self.name} "
            f"(id={getattr(self, 'id', 'N/A')}, is_expert={self._is_expert_agent})"
        )

        # Process file and media blocks in messages
        if msg is not None:
            await process_file_and_media_blocks_in_message(msg)

        # Check if message is a system command
        last_msg = msg[-1] if isinstance(msg, list) else msg
        query = (
            last_msg.get_text_content() if isinstance(last_msg, Msg) else None
        )

        if self.command_handler.is_command(query):
            logger.info(f"Received command: {query}")
            msg = await self.command_handler.handle_command(query)
            await self.print(msg)
            return msg

        # Multi-agent routing (Phase 1)
        # Only the main PM agent performs routing, expert agents process directly
        if not self._is_expert_agent and self._agent_router is not None:
            # Get channel and user_id from memory or instance variables
            # For now, use the instance variables set during initialization
            logger.info(
                f"[路由决策] 开始路由 - 当前 agent: {self.name} (id={getattr(self, 'id', 'N/A')}), "
                f"channel={self._channel or 'console'}, user_id={self._user_id or 'default'}"
            )

            routing_result = await self._agent_router.route_request(
                channel=self._channel or "console",
                user_id=self._user_id or "default",
                message=query,
            )

            # If a different agent is matched, delegate to it
            if (
                routing_result.matched_instance is not None
                and routing_result.matched_instance.id != getattr(self, 'id', None)
            ):
                logger.info(
                    f"[路由决策] 路由到专家 agent: {routing_result.matched_instance.name} "
                    f"(id={routing_result.matched_instance.id}, type={routing_result.matched_instance.agent_type})\n"
                    f"  - 路由原因：{routing_result.reason}\n"
                    f"  - 优先级分数：{routing_result.priority_score}\n"
                    f"  - 候选 agent 数量：{len(routing_result.all_candidates)}\n"
                    f"  - 当前处理 agent: {self.name} (将进行委托)"
                )

                # Process with the matched expert agent
                # Note: We get the agent instance and call reply directly so that
                # the stream_printing_messages pipeline can capture its output
                if self._agent_instance_manager is not None:
                    expert_agent = await self._agent_instance_manager.get_or_create_agent(
                        instance_id=routing_result.matched_instance.id,
                        channel=self._channel,
                        user_id=self._user_id,
                        session_id=self._session_id,
                    )
                    if expert_agent is None:
                        raise ValueError(
                            f"Agent instance {routing_result.matched_instance.id} not found"
                        )
                    # Enable message queue for the expert agent so its output
                    # can be captured by stream_printing_messages in the runner
                    if hasattr(self, 'msg_queue') and self.msg_queue is not None:
                        expert_agent.set_msg_queue_enabled(True, self.msg_queue)
                    # Share the same memory with the main agent so that conversation
                    # history is saved correctly
                    expert_agent.memory = self.memory
                    # The expert agent will use the same msg_queue and memory as this agent
                    logger.info(
                        f"[路由决策] 开始委托 - 消息将由 '{expert_agent.name}' 处理 (id={getattr(expert_agent, 'id', 'N/A')})"
                    )
                    return await expert_agent.reply(msg=msg, structured_model=structured_model)

            # No routing needed - process with current agent
            logger.info(
                f"[路由决策] 无需路由 - 当前 agent '{self.name}' 直接处理消息 "
                f"(routing_result.matched_instance={routing_result.matched_instance.name if routing_result.matched_instance else 'None'})"
            )

        # Expert agent processing directly (no routing)
        elif self._is_expert_agent:
            logger.info(
                f"[Agent 处理] 专家 agent '{self.name}' 直接处理消息 (跳过路由)"
            )

        # Normal message processing (no routing or expert agent)
        return await super().reply(msg=msg, structured_model=structured_model)
