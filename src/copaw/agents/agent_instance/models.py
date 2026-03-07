# -*- coding: utf-8 -*-
"""Agent Instance models for CoPaw multi-agent system.

This module defines data models for agent instance specification
and management, enabling multi-agent routing based on scope.

Example:
    >>> from copaw.agents.agent_instance import AgentInstance, AgentScope
    >>>
    >>> # Create a teacher agent for specific users
    >>> agent = AgentInstance(
    ...     name="中学优秀教师",
    ...     description="20 年资深经验的中学优秀教师，擅长教学和学生辅导",
    ...     agent_type="teacher",
    ...     system_prompt="你是一位拥有 20 年教学经验的中学优秀教师...",
    ...     scope=AgentScope.USER,
    ...     user_ids="user1 user2 user3",
    ... )
"""
from enum import Enum
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from uuid import uuid4


class AgentScope(str, Enum):
    """Agent instance application scope.

    Defines where an agent applies:
    - GLOBAL: Default agent for all contexts
    - CHANNEL: Agent for specific channel (e.g., dingtalk, feishu)
    - USER: Agent for specific users across channels
    - USER_CHANNEL: Agent for specific users in specific channel
    """
    GLOBAL = "global"
    CHANNEL = "channel"
    USER = "user"
    USER_CHANNEL = "user_channel"


class ModelConfig(BaseModel):
    """LLM model configuration for an agent instance.

    Attributes:
        model_name: Model identifier (e.g., "qwen3.5-plus")
        temperature: Sampling temperature (0.0-2.0)
        max_tokens: Maximum tokens in response
        base_url: Optional custom API base URL
        api_key: Optional custom API key
    """
    model_name: Optional[str] = None
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None


class AgentInstance(BaseModel):
    """Agent instance specification.

    An agent instance represents a specialized AI agent configured
    for specific contexts (channels, users).

    Attributes:
        id: Unique identifier for the agent instance
        name: Display name (e.g., "中学优秀教师", "技术专家")
        description: Human-readable description
        agent_type: Type identifier for agent selection logic
        system_prompt: Complete system prompt for this agent
        scope: The scope of agent application
        channel: Channel name (for CHANNEL/USER_CHANNEL scope)
        user_ids: Space-separated user identifiers (for USER/USER_CHANNEL scope)
        llm_config: Optional LLM model configuration overrides
        enabled: Whether the agent instance is currently active
        created_at: When the agent instance was created
        updated_at: When the agent instance was last updated
    """
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    description: str
    agent_type: str = "custom"  # custom, teacher, expert, investor, etc.
    system_prompt: str

    # Scope configuration
    scope: AgentScope = AgentScope.GLOBAL
    channel: Optional[str] = None
    user_ids: Optional[str] = None  # Space-separated user IDs

    # LLM configuration (optional overrides)
    llm_config: Optional[ModelConfig] = Field(default=None, alias="model_config")

    # Status
    enabled: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {
        "populate_by_name": True,
        "json_encoders": {
            datetime: lambda v: v.isoformat(),
            AgentScope: lambda v: v.value,
        }
    }

    @property
    def user_id_list(self) -> list[str]:
        """Get list of user IDs from space-separated string."""
        if not self.user_ids:
            return []
        return [uid.strip() for uid in self.user_ids.split() if uid.strip()]

    def is_applicable_to(
        self,
        channel: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> bool:
        """Check if this agent instance applies to the given context.

        Args:
            channel: Channel name to check
            user_id: User ID to check

        Returns:
            True if the agent instance applies to the given context
        """
        if not self.enabled:
            return False

        if self.scope == AgentScope.GLOBAL:
            return True
        elif self.scope == AgentScope.CHANNEL:
            return self.channel == channel
        elif self.scope == AgentScope.USER:
            return user_id in self.user_id_list
        elif self.scope == AgentScope.USER_CHANNEL:
            return (
                self.channel == channel and
                user_id in self.user_id_list
            )

        return False

    def get_priority_score(
        self,
        channel: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> int:
        """Get priority score for agent selection.

        Higher score = more specific = higher priority.

        Args:
            channel: Channel name
            user_id: User ID

        Returns:
            Priority score (0 if not applicable, 1-4 if applicable)
        """
        if not self.is_applicable_to(channel=channel, user_id=user_id):
            return 0

        # Priority order: GLOBAL < CHANNEL < USER < USER_CHANNEL
        if self.scope == AgentScope.GLOBAL:
            return 1
        elif self.scope == AgentScope.CHANNEL:
            return 2
        elif self.scope == AgentScope.USER:
            return 3
        elif self.scope == AgentScope.USER_CHANNEL:
            return 4

        return 0


__all__ = ["AgentScope", "AgentInstance", "ModelConfig"]
