# -*- coding: utf-8 -*-
"""Security Guard Rules API Router for CoPaw."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from enum import Enum

from ...security.tool_guard import (
    SecurityGuardManager,
    RuleCategory,
    RuleSeverity,
    RuleScope,
    SecurityGuardRuleSpec,
)

router = APIRouter(prefix="/security", tags=["security"])

# Global security guard manager instance
_security_guard_manager: Optional[SecurityGuardManager] = None


def set_security_guard_manager(manager: SecurityGuardManager):
    """Set the security guard manager instance."""
    global _security_guard_manager
    _security_guard_manager = manager


def get_security_guard_manager() -> SecurityGuardManager:
    """Get the security guard manager instance."""
    if _security_guard_manager is None:
        raise HTTPException(status_code=500, detail="Security guard manager not initialized")
    return _security_guard_manager


class RuleCategoryEnum(str, Enum):
    """Rule category enum for API."""
    CONTENT_SAFETY = "content_safety"
    DATA_PRIVACY = "data_privacy"
    SYSTEM_SECURITY = "system_security"
    ETHICAL_GUIDELINES = "ethical_guidelines"
    COMPLIANCE = "compliance"
    CUSTOM = "custom"


class RuleSeverityEnum(str, Enum):
    """Rule severity enum for API."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RuleScopeEnum(str, Enum):
    """Rule scope enum for API."""
    GLOBAL = "global"
    AGENT = "agent"
    CHANNEL = "channel"
    USER = "user"


class SecurityRuleCreate(BaseModel):
    """Security rule creation model."""
    name: str
    description: str
    category: RuleCategoryEnum = RuleCategoryEnum.CUSTOM
    severity: RuleSeverityEnum = RuleSeverityEnum.MEDIUM
    scope: RuleScopeEnum = RuleScopeEnum.GLOBAL
    patterns: List[str] = []
    blocked_actions: List[str] = []
    target_agents: Optional[List[str]] = None
    target_channels: Optional[List[str]] = None
    target_users: Optional[List[str]] = None


class SecurityRuleUpdate(BaseModel):
    """Security rule update model."""
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[RuleCategoryEnum] = None
    severity: Optional[RuleSeverityEnum] = None
    scope: Optional[RuleScopeEnum] = None
    patterns: Optional[List[str]] = None
    blocked_actions: Optional[List[str]] = None
    enabled: Optional[bool] = None
    target_agents: Optional[List[str]] = None
    target_channels: Optional[List[str]] = None
    target_users: Optional[List[str]] = None


@router.get("")
async def list_rules(
    category: Optional[str] = None,
    enabled_only: bool = False,
):
    """List all security rules with optional filters.

    Args:
        category: Filter by category
        enabled_only: If True, only return enabled rules

    Returns:
        List of security rules
    """
    manager = get_security_guard_manager()
    config = manager.get_config()
    rules = config.rules

    # Apply filters
    if category:
        rules = [r for r in rules if r.category.value == category]
    if enabled_only:
        rules = [r for r in rules if r.enabled]

    return {"rules": [rule.model_dump() for rule in rules]}


@router.get("/state")
async def get_security_state():
    """Get current security guard state.

    Returns:
        Security guard state including rule counts and violation stats
    """
    manager = get_security_guard_manager()
    state = manager.get_state()
    return {"state": state.model_dump()}


@router.post("")
async def create_rule(rule: SecurityRuleCreate):
    """Create a new security rule.

    Args:
        rule: Rule specification

    Returns:
        Created rule
    """
    manager = get_security_guard_manager()
    spec = SecurityGuardRuleSpec(
        name=rule.name,
        description=rule.description,
        category=RuleCategory(rule.category.value),
        severity=RuleSeverity(rule.severity.value),
        scope=RuleScope(rule.scope.value),
        patterns=rule.patterns,
        blocked_actions=rule.blocked_actions,
        target_agents=rule.target_agents,
        target_channels=rule.target_channels,
        target_users=rule.target_users,
    )
    new_rule = await manager.add_rule(spec)
    return {"rule": new_rule.model_dump()}


@router.get("/{rule_id}")
async def get_rule(rule_id: str):
    """Get a specific security rule by ID.

    Args:
        rule_id: Rule ID

    Returns:
        Rule details
    """
    manager = get_security_guard_manager()
    config = manager.get_config()
    rule = next((r for r in config.rules if r.id == rule_id), None)

    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    return {"rule": rule.model_dump()}


@router.put("/{rule_id}")
async def update_rule(rule_id: str, updates: SecurityRuleUpdate):
    """Update an existing security rule.

    Args:
        rule_id: Rule ID to update
        updates: Fields to update

    Returns:
        Updated rule
    """
    manager = get_security_guard_manager()

    # Build update dict (only non-None fields)
    update_dict = {k: v for k, v in updates.model_dump().items() if v is not None}

    # Convert enum values to string values
    if "category" in update_dict:
        update_dict["category"] = update_dict["category"].value
    if "severity" in update_dict:
        update_dict["severity"] = update_dict["severity"].value
    if "scope" in update_dict:
        update_dict["scope"] = update_dict["scope"].value

    updated_rule = await manager.update_rule(rule_id, update_dict)

    if not updated_rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    return {"rule": updated_rule.model_dump()}


@router.delete("/{rule_id}")
async def delete_rule(rule_id: str):
    """Delete a security rule.

    Args:
        rule_id: Rule ID to delete

    Returns:
        Success status
    """
    manager = get_security_guard_manager()
    deleted = await manager.delete_rule(rule_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Rule not found")

    return {"success": True}


@router.post("/{rule_id}/enable")
async def enable_rule(rule_id: str):
    """Enable a security rule.

    Args:
        rule_id: Rule ID to enable

    Returns:
        Updated rule
    """
    manager = get_security_guard_manager()
    updated = await manager.enable_rule(rule_id)

    if not updated:
        raise HTTPException(status_code=404, detail="Rule not found")

    return {"rule": updated.model_dump()}


@router.post("/{rule_id}/disable")
async def disable_rule(rule_id: str):
    """Disable a security rule.

    Args:
        rule_id: Rule ID to disable

    Returns:
        Updated rule
    """
    manager = get_security_guard_manager()
    updated = await manager.disable_rule(rule_id)

    if not updated:
        raise HTTPException(status_code=404, detail="Rule not found")

    return {"rule": updated.model_dump()}


@router.get("/violations/list")
async def list_violations(
    limit: int = 100,
    rule_id: Optional[str] = None,
    user_id: Optional[str] = None,
):
    """List security rule violations.

    Args:
        limit: Max violations to return
        rule_id: Filter by rule ID
        user_id: Filter by user ID

    Returns:
        List of violations
    """
    manager = get_security_guard_manager()
    violations = manager.get_violations(
        limit=limit,
        rule_id=rule_id,
        user_id=user_id,
    )
    return {"violations": [v.model_dump() for v in violations]}


@router.post("/check")
async def check_input(
    input_text: str,
    agent_type: Optional[str] = None,
    channel: Optional[str] = None,
    user_id: Optional[str] = None,
):
    """Check if input violates any security rules.

    Args:
        input_text: Input text to check
        agent_type: Optional agent type context
        channel: Optional channel context
        user_id: Optional user ID context

    Returns:
        Check result with violation details if any
    """
    manager = get_security_guard_manager()
    is_safe, violated_rule, matched_pattern = manager.check_input(
        input_text=input_text,
        agent_type=agent_type,
        channel=channel,
        user_id=user_id,
    )

    return {
        "is_safe": is_safe,
        "violated_rule": violated_rule.model_dump() if violated_rule else None,
        "matched_pattern": matched_pattern,
    }
