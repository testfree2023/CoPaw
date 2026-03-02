# -*- coding: utf-8 -*-
"""Rules API Router for CoPaw."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from enum import Enum

from ...agents.rules import RuleManager, RuleScope, RuleSpec

router = APIRouter(prefix="/rules", tags=["rules"])

# Global rule manager instance
_rule_manager: Optional[RuleManager] = None


def set_rule_manager(manager: RuleManager):
    """Set the rule manager instance."""
    global _rule_manager
    _rule_manager = manager


def get_rule_manager() -> RuleManager:
    """Get the rule manager instance."""
    if _rule_manager is None:
        raise HTTPException(status_code=500, detail="Rule manager not initialized")
    return _rule_manager


class RuleScopeEnum(str, Enum):
    """Rule scope enum for API."""
    GLOBAL = "GLOBAL"
    CHANNEL = "CHANNEL"
    USER = "USER"
    SESSION = "SESSION"


class RuleCreate(BaseModel):
    """Rule creation model."""
    content: str
    scope: RuleScopeEnum = RuleScopeEnum.GLOBAL
    priority: int = 0
    channel: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    description: Optional[str] = None


class RuleUpdate(BaseModel):
    """Rule update model."""
    content: Optional[str] = None
    priority: Optional[int] = None
    description: Optional[str] = None
    enabled: Optional[bool] = None


@router.get("")
async def list_rules():
    """List all rules."""
    manager = get_rule_manager()
    rules = await manager.list_rules()
    return {"rules": [rule.model_dump() for rule in rules]}


@router.post("")
async def create_rule(rule: RuleCreate):
    """Create a new rule."""
    manager = get_rule_manager()
    new_rule = await manager.add_rule(
        content=rule.content,
        scope=RuleScope(rule.scope.value),
        priority=rule.priority,
        channel=rule.channel,
        user_id=rule.user_id,
        session_id=rule.session_id,
        description=rule.description,
    )
    return {"rule": new_rule.model_dump()}


@router.get("/{rule_id}")
async def get_rule(rule_id: str):
    """Get a specific rule."""
    manager = get_rule_manager()
    rule = await manager.get_rule(rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    return {"rule": rule.model_dump()}


@router.put("/{rule_id}")
async def update_rule(rule_id: str, rule: RuleUpdate):
    """Update a rule."""
    manager = get_rule_manager()
    updates = rule.model_dump(exclude_unset=True)
    updated_rule = await manager.update_rule(rule_id, **updates)
    if updated_rule is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    return {"rule": updated_rule.model_dump()}


@router.delete("/{rule_id}")
async def delete_rule(rule_id: str):
    """Delete a rule."""
    manager = get_rule_manager()
    success = await manager.remove_rule(rule_id)
    if not success:
        raise HTTPException(status_code=404, detail="Rule not found")
    return {"success": True}


@router.post("/{rule_id}/toggle")
async def toggle_rule(rule_id: str):
    """Toggle rule enabled status."""
    manager = get_rule_manager()
    rule = await manager.get_rule(rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    updated_rule = await manager.update_rule(rule_id, enabled=not rule.enabled)
    return {"rule": updated_rule.model_dump()}