# -*- coding: utf-8 -*-
"""Agent Instance API Router for CoPaw."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from enum import Enum

from ...agents.agent_instance import (
    AgentInstanceManager,
    AgentScope,
    AgentInstance,
    ModelConfig,
)

router = APIRouter(prefix="/agent-instances", tags=["agent-instances"])

# Global agent instance manager instance
_manager: Optional[AgentInstanceManager] = None


def set_manager(manager: AgentInstanceManager):
    """Set the agent instance manager instance."""
    global _manager
    _manager = manager


def get_manager() -> AgentInstanceManager:
    """Get the agent instance manager instance."""
    if _manager is None:
        raise HTTPException(status_code=500, detail="Agent instance manager not initialized")
    return _manager


class AgentScopeEnum(str, Enum):
    """Agent scope enum for API."""
    GLOBAL = "global"
    CHANNEL = "channel"
    USER = "user"
    USER_CHANNEL = "user_channel"


class ModelConfigInput(BaseModel):
    """Model config input model."""
    model_name: Optional[str] = None
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None


class AgentInstanceCreate(BaseModel):
    """Agent instance creation model."""
    name: str
    description: str
    agent_type: str = "custom"
    system_prompt: str
    scope: AgentScopeEnum = AgentScopeEnum.GLOBAL
    channel: Optional[str] = None
    user_ids: Optional[str] = None
    llm_config: Optional[ModelConfigInput] = Field(default=None, alias="model_config")

    model_config = ConfigDict(populate_by_name=True)


class AgentInstanceUpdate(BaseModel):
    """Agent instance update model."""
    name: Optional[str] = None
    description: Optional[str] = None
    agent_type: Optional[str] = None
    system_prompt: Optional[str] = None
    scope: Optional[str] = None
    channel: Optional[str] = None
    user_ids: Optional[str] = None
    llm_config: Optional[dict] = Field(default=None, alias="model_config")

    model_config = ConfigDict(populate_by_name=True)
    enabled: Optional[bool] = None


@router.get("")
async def list_instances():
    """List all agent instances."""
    manager = get_manager()
    instances = await manager.list_instances()
    return {"instances": [inst.model_dump() for inst in instances]}


@router.post("")
async def create_instance(instance: AgentInstanceCreate):
    """Create a new agent instance."""
    manager = get_manager()
    new_instance = await manager.create_instance(
        name=instance.name,
        description=instance.description,
        agent_type=instance.agent_type,
        system_prompt=instance.system_prompt,
        scope=AgentScope(instance.scope.value),
        channel=instance.channel,
        user_ids=instance.user_ids,
        model_config=instance.model_config,
    )
    return {"instance": new_instance.model_dump()}


@router.get("/{instance_id}")
async def get_instance(instance_id: str):
    """Get a specific agent instance."""
    manager = get_manager()
    instance = await manager.get_instance(instance_id)
    if instance is None:
        raise HTTPException(status_code=404, detail="Agent instance not found")
    return {"instance": instance.model_dump()}


@router.put("/{instance_id}")
async def update_instance(instance_id: str, instance: AgentInstanceUpdate):
    """Update an agent instance."""
    manager = get_manager()
    updates = instance.model_dump(exclude_unset=True)
    updated_instance = await manager.update_instance(instance_id, **updates)
    if updated_instance is None:
        raise HTTPException(status_code=404, detail="Agent instance not found")
    return {"instance": updated_instance.model_dump()}


@router.delete("/{instance_id}")
async def delete_instance(instance_id: str):
    """Delete an agent instance."""
    manager = get_manager()
    success = await manager.delete_instance(instance_id)
    if not success:
        raise HTTPException(status_code=404, detail="Agent instance not found")
    return {"success": True}


@router.post("/{instance_id}/toggle")
async def toggle_instance(instance_id: str):
    """Toggle agent instance enabled status."""
    manager = get_manager()
    instance = await manager.get_instance(instance_id)
    if instance is None:
        raise HTTPException(status_code=404, detail="Agent instance not found")
    if instance.enabled:
        await manager.disable_instance(instance_id)
    else:
        await manager.enable_instance(instance_id)
    updated_instance = await manager.get_instance(instance_id)
    return {"instance": updated_instance.model_dump()}


@router.post("/test-route")
async def test_route(channel: str, user_id: str, message: Optional[str] = None):
    """Test agent routing for a given context.

    Args:
        channel: Channel name to test
        user_id: User ID to test
        message: Optional message content

    Returns:
        Routing result with matched agent and reasoning
    """
    from .router import AgentRouter

    manager = get_manager()
    router = AgentRouter(manager)

    result = await router.route_request(channel=channel, user_id=user_id, message=message)

    return {
        "matched_instance": result.matched_instance.model_dump() if result.matched_instance else None,
        "reason": result.reason,
        "priority_score": result.priority_score,
        "candidates": [inst.model_dump() for inst in result.all_candidates],
    }
