# -*- coding: utf-8 -*-
"""Agent Instance Manager for CoPaw multi-agent system.

This module provides agent instance management capabilities for CoPaw,
enabling multi-agent routing based on scope and user/channel context.

Features:
- Create, read, update, delete agent instances
- Scope-based agent instance application
- Priority-based selection (USER_CHANNEL > USER > CHANNEL > GLOBAL)
- Persistent storage with JSON backend
- Agent instance caching for performance
- Lazy loading of CoPawAgent instances

Example:
    >>> from copaw.agents.agent_instance import AgentInstanceManager, AgentScope
    >>>
    >>> manager = AgentInstanceManager()
    >>> await manager.load()
    >>>
    >>> # Create a teacher agent for specific users
    >>> await manager.create_instance(
    ...     name="中学优秀教师",
    ...     description="20 年资深经验的中学优秀教师",
    ...     agent_type="teacher",
    ...     system_prompt="你是一位拥有 20 年教学经验的中学优秀教师...",
    ...     scope=AgentScope.USER,
    ...     user_ids="user1 user2",
    ... )
    >>>
    >>> # Get active agent for context
    >>> agent = await manager.get_active_instance(
    ...     channel="dingtalk",
    ...     user_id="user1",
    ... )
"""
import json
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any

from .models import AgentInstance, AgentScope, ModelConfig

__all__ = ["AgentInstanceManager"]

# Forward reference to avoid circular import
_CoPawAgent = Any


class AgentInstanceManager:
    """Agent instance manager for multi-agent routing.

    This manager handles:
    - Agent instance CRUD operations
    - Scope-based agent instance filtering
    - Priority-based selection
    - JSON file persistence
    - In-memory caching of CoPawAgent instances

    Attributes:
        save_dir: Directory where agent instances are stored
        instances_file: Path to the agent_instances.json file
    """

    def __init__(
        self,
        save_dir: str = "~/.copaw/agent_instances",
        enable_memory_manager: bool = True,
        mcp_clients: Optional[List] = None,
    ):
        """Initialize AgentInstanceManager.

        Args:
            save_dir: Directory to store agent instance files
            enable_memory_manager: Whether to enable memory manager for agent instances
            mcp_clients: Optional list of MCP clients for tool integration
        """
        self.save_dir = Path(save_dir).expanduser()
        self.save_dir.mkdir(parents=True, exist_ok=True)

        self._instances: Dict[str, AgentInstance] = {}
        self._agent_cache: Dict[str, _CoPawAgent] = {}  # Cache of CoPawAgent instances
        self._lock = asyncio.Lock()
        self._instances_file = self.save_dir / "agent_instances.json"

        # Configuration for creating CoPawAgent instances
        self._enable_memory_manager = enable_memory_manager
        self._mcp_clients = mcp_clients or []

    @property
    def instances_file(self) -> Path:
        """Get the agent instances file path."""
        return self._instances_file

    async def load(self) -> None:
        """Load agent instances from disk.

        Reads agent_instances.json and populates the in-memory cache.
        If the file doesn't exist, starts with an empty agent instance set.
        """
        async with self._lock:
            if not self._instances_file.exists():
                return

            try:
                data = json.loads(self._instances_file.read_text(encoding="utf-8"))
                for instance_data in data.get("instances", []):
                    instance = AgentInstance(**instance_data)
                    self._instances[instance.id] = instance
            except (json.JSONDecodeError, KeyError) as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Failed to load agent instances: {e}")

    async def save(self) -> None:
        """Save agent instances to disk."""
        async with self._lock:
            await self._persist()

    async def create_instance(
        self,
        name: str,
        description: str,
        agent_type: str,
        system_prompt: str,
        scope: AgentScope = AgentScope.GLOBAL,
        channel: Optional[str] = None,
        user_ids: Optional[str] = None,
        model_config: Optional[ModelConfig] = None,
        enabled: bool = True,
    ) -> AgentInstance:
        """Create a new agent instance.

        Args:
            name: Agent instance display name
            description: Human-readable description
            agent_type: Type identifier (e.g., "teacher", "expert")
            system_prompt: Complete system prompt for this agent
            scope: Agent instance application scope
            channel: Channel name (for CHANNEL/USER_CHANNEL scope)
            user_ids: Space-separated user IDs (for USER/USER_CHANNEL scope)
            model_config: Optional model configuration overrides
            enabled: Whether the agent instance is initially enabled

        Returns:
            The created AgentInstance

        Raises:
            ValueError: If scope-channel/user_ids mismatch
        """
        # Validate scope-specific fields
        if scope in (AgentScope.CHANNEL, AgentScope.USER_CHANNEL) and not channel:
            raise ValueError("channel is required for CHANNEL/USER_CHANNEL scope")
        if scope in (AgentScope.USER, AgentScope.USER_CHANNEL) and not user_ids:
            raise ValueError("user_ids is required for USER/USER_CHANNEL scope")

        instance = AgentInstance(
            name=name,
            description=description,
            agent_type=agent_type,
            system_prompt=system_prompt,
            scope=scope,
            channel=channel,
            user_ids=user_ids,
            model_config=model_config,
            enabled=enabled,
        )

        async with self._lock:
            self._instances[instance.id] = instance
            await self._persist()

        return instance

    async def get_instance(self, instance_id: str) -> Optional[AgentInstance]:
        """Get an agent instance by ID."""
        async with self._lock:
            return self._instances.get(instance_id)

    async def delete_instance(self, instance_id: str) -> bool:
        """Delete an agent instance by ID."""
        async with self._lock:
            if instance_id not in self._instances:
                return False
            del self._instances[instance_id]
            await self._persist()
            return True

    async def update_instance(
        self,
        instance_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        agent_type: Optional[str] = None,
        system_prompt: Optional[str] = None,
        scope: Optional[str] = None,
        channel: Optional[str] = None,
        user_ids: Optional[str] = None,
        model_config: Optional[dict] = None,
        enabled: Optional[bool] = None,
    ) -> Optional[AgentInstance]:
        """Update an existing agent instance."""
        async with self._lock:
            if instance_id not in self._instances:
                return None

            instance = self._instances[instance_id]
            if name is not None:
                instance.name = name
            if description is not None:
                instance.description = description
            if agent_type is not None:
                instance.agent_type = agent_type
            if system_prompt is not None:
                instance.system_prompt = system_prompt
            if scope is not None:
                instance.scope = AgentScope(scope)
            if channel is not None:
                instance.channel = channel
            if user_ids is not None:
                instance.user_ids = user_ids
            if model_config is not None:
                instance.model_config = ModelConfig(**model_config) if model_config else None
            if enabled is not None:
                instance.enabled = enabled
            instance.updated_at = datetime.now(timezone.utc)

            await self._persist()
            return instance

    async def list_instances(
        self,
        scope: Optional[AgentScope] = None,
        enabled_only: bool = True,
    ) -> List[AgentInstance]:
        """List all agent instances with optional filtering."""
        async with self._lock:
            instances = []
            for inst in self._instances.values():
                if enabled_only and not inst.enabled:
                    continue
                if scope is not None and inst.scope != scope:
                    continue
                instances.append(inst)
            return instances

    async def get_active_instance(
        self,
        channel: str,
        user_id: str,
    ) -> Optional[AgentInstance]:
        """Get the active agent instance for the given context.

        Selects the agent instance with highest priority score:
        - USER_CHANNEL (4) > USER (3) > CHANNEL (2) > GLOBAL (1)

        Args:
            channel: Channel name
            user_id: User identifier

        Returns:
            The AgentInstance with highest priority, or None if no agent instance applies
        """
        async with self._lock:
            candidates = []
            for instance in self._instances.values():
                score = instance.get_priority_score(
                    channel=channel,
                    user_id=user_id,
                )
                if score > 0:
                    candidates.append((score, instance))

            if not candidates:
                return None

            # Sort by score (highest first)
            candidates.sort(key=lambda x: x[0], reverse=True)
            return candidates[0][1]

    async def enable_instance(self, instance_id: str) -> bool:
        """Enable an agent instance."""
        async with self._lock:
            if instance_id not in self._instances:
                return False
            self._instances[instance_id].enabled = True
            await self._persist()
            return True

    async def disable_instance(self, instance_id: str) -> bool:
        """Disable an agent instance."""
        async with self._lock:
            if instance_id not in self._instances:
                return False
            self._instances[instance_id].enabled = False
            await self._persist()
            return True

    async def _persist(self) -> None:
        """Persist agent instances to disk atomically."""
        from datetime import datetime
        data = {
            "version": 1,
            "instances": [
                inst.model_dump(mode="json")
                for inst in self._instances.values()
            ],
        }

        tmp_path = self._instances_file.with_suffix(".tmp")
        tmp_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        tmp_path.replace(self._instances_file)

    async def clear_all(self) -> None:
        """Clear all agent instances."""
        async with self._lock:
            self._instances.clear()
            self._agent_cache.clear()
            await self._persist()

    async def get_or_create_agent(
        self,
        instance_id: str,
        channel: Optional[str] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> Optional[_CoPawAgent]:
        """Get or create a CoPawAgent instance for the given agent instance.

        Uses lazy loading - creates the CoPawAgent on first request and caches it.

        Args:
            instance_id: The agent instance ID
            channel: Channel name for context-aware processing
            user_id: User identifier for context-aware processing
            session_id: Session identifier for context-aware processing

        Returns:
            CoPawAgent instance or None if agent instance not found
        """
        async with self._lock:
            # Check cache first
            if instance_id in self._agent_cache:
                return self._agent_cache[instance_id]

            # Get agent instance
            instance = self._instances.get(instance_id)
            if instance is None:
                return None

            # Create CoPawAgent instance
            agent = await self._create_agent(
                instance=instance,
                channel=channel,
                user_id=user_id,
                session_id=session_id,
            )

            # Cache the agent
            self._agent_cache[instance_id] = agent
            return agent

    async def _create_agent(
        self,
        instance: AgentInstance,
        channel: Optional[str] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> _CoPawAgent:
        """Create a CoPawAgent instance from an AgentInstance.

        Args:
            instance: The agent instance specification
            channel: Channel name for context-aware processing
            user_id: User identifier for context-aware processing
            session_id: Session identifier for context-aware processing

        Returns:
            CoPawAgent instance
        """
        # Lazy import to avoid circular dependency
        from ..react_agent import CoPawAgent

        # Build env_context (optional prepend to system prompt)
        env_context = None

        # Create CoPawAgent with instance-specific configuration
        agent = CoPawAgent(
            name=instance.name,  # Use agent instance name
            env_context=env_context,
            enable_memory_manager=self._enable_memory_manager,
            mcp_clients=self._mcp_clients,
            max_input_length=128 * 1024,  # Configurable
            channel=channel,
            user_id=user_id,
            session_id=session_id,
        )

        # Override system prompt with instance-specific prompt
        # Note: We need to set this after initialization
        agent._sys_prompt = instance.system_prompt

        # Update memory's first system message if exists
        for msg, _marks in agent.memory.content:
            if msg.role == "system":
                msg.content = instance.system_prompt
                break

        return agent

    async def invalidate_agent_cache(self, instance_id: Optional[str] = None) -> None:
        """Invalidate cached CoPawAgent instances.

        Args:
            instance_id: Specific instance to invalidate, or None to clear all
        """
        async with self._lock:
            if instance_id is not None:
                self._agent_cache.pop(instance_id, None)
            else:
                self._agent_cache.clear()

    async def process_with_agent(
        self,
        instance_id: str,
        msg: Any,
        channel: Optional[str] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> Any:
        """Process a message with a specific agent instance.

        Args:
            instance_id: The agent instance ID
            msg: Input message(s) from user
            channel: Channel name for context-aware processing
            user_id: User identifier for context-aware processing
            session_id: Session identifier for context-aware processing

        Returns:
            Response message from the agent
        """
        agent = await self.get_or_create_agent(
            instance_id=instance_id,
            channel=channel,
            user_id=user_id,
            session_id=session_id,
        )

        if agent is None:
            raise ValueError(f"Agent instance {instance_id} not found")

        return await agent.reply(msg)
