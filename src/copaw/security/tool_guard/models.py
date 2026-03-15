# -*- coding: utf-8 -*-
"""Security guard models for CoPaw.

This module defines the data models for security guard rules that constrain
agent behavior and prevent harmful outputs.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class RuleCategory(str, Enum):
    """Category of security rule."""

    CONTENT_SAFETY = "content_safety"  # Prevent harmful content generation
    DATA_PRIVACY = "data_privacy"  # Protect sensitive data
    SYSTEM_SECURITY = "system_security"  # Prevent system compromise
    ETHICAL_GUIDELINES = "ethical_guidelines"  # Ethical behavior constraints
    COMPLIANCE = "compliance"  # Legal and regulatory compliance
    CUSTOM = "custom"  # User-defined custom rules


class RuleSeverity(str, Enum):
    """Severity level of security rule violation."""

    CRITICAL = "critical"  # Must block immediately
    HIGH = "high"  # Strong warning, likely block
    MEDIUM = "medium"  # Warn user, may proceed with caution
    LOW = "low"  # Informational, log only


class RuleScope(str, Enum):
    """Scope of rule application."""

    GLOBAL = "global"  # Apply to all agents and channels
    AGENT = "agent"  # Apply to specific agent type
    CHANNEL = "channel"  # Apply to specific channel
    USER = "user"  # Apply to specific user


class SecurityGuardRule(BaseModel):
    """A single security guard rule.

    Attributes:
        id: Unique rule identifier
        name: Human-readable rule name
        description: Detailed description of what the rule prevents
        category: Rule category for organization
        severity: How strictly to enforce
        scope: Where this rule applies
        patterns: List of patterns to detect (keywords, regex, etc.)
        blocked_actions: Actions to take when rule is violated
        enabled: Whether rule is active
        created_at: Rule creation timestamp
        updated_at: Last modification timestamp
    """

    id: str
    name: str
    description: str
    category: RuleCategory
    severity: RuleSeverity
    scope: RuleScope = RuleScope.GLOBAL
    patterns: List[str] = Field(default_factory=list)
    blocked_actions: List[str] = Field(default_factory=list)
    enabled: bool = True
    target_agents: Optional[List[str]] = None  # Agent types this applies to
    target_channels: Optional[List[str]] = None  # Channels this applies to
    target_users: Optional[List[str]] = None  # Users this applies to
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    model_config = ConfigDict(
        json_encoders={datetime: lambda v: v.isoformat()},
        use_enum_values=True,
    )


class SecurityGuardRuleSpec(BaseModel):
    """Specification for creating or updating a rule.

    Used for API requests to create/update rules without requiring
    all fields of SecurityGuardRule.
    """

    name: str
    description: str
    category: RuleCategory
    severity: RuleSeverity
    scope: RuleScope = RuleScope.GLOBAL
    patterns: List[str] = Field(default_factory=list)
    blocked_actions: List[str] = Field(default_factory=list)
    enabled: bool = True
    target_agents: Optional[List[str]] = None
    target_channels: Optional[List[str]] = None
    target_users: Optional[List[str]] = None


class SecurityGuardConfig(BaseModel):
    """Configuration for security guard system.

    Attributes:
        version: Config file version
        rules: List of security rules
        enabled: Whether security guard is enabled globally
        default_severity: Default severity for new rules
        log_violations: Whether to log rule violations
        notify_on_violation: Whether to notify on violations
    """

    version: int = 1
    rules: List[SecurityGuardRule] = Field(default_factory=list)
    enabled: bool = True
    default_severity: RuleSeverity = RuleSeverity.MEDIUM
    log_violations: bool = True
    notify_on_violation: bool = False

    model_config = ConfigDict(use_enum_values=True)

    def get_enabled_rules(self) -> List[SecurityGuardRule]:
        """Get all enabled rules sorted by severity."""
        severity_order = {
            "critical": 0,
            "high": 1,
            "medium": 2,
            "low": 3,
        }
        enabled_rules = [r for r in self.rules if r.enabled]
        return sorted(
            enabled_rules,
            key=lambda r: severity_order.get(r.severity, 99),
        )


class RuleViolationRecord(BaseModel):
    """Record of a rule violation.

    Attributes:
        id: Unique violation identifier
        rule_id: ID of the violated rule
        rule_name: Name of the violated rule
        triggered_at: When the violation occurred
        input_content: The input that triggered the rule
        matched_pattern: The pattern that was matched
        agent_type: Agent that was constrained
        channel: Channel where violation occurred
        user_id: User who made the request
        action_taken: What action was taken
    """

    id: str
    rule_id: str
    rule_name: str
    triggered_at: datetime
    input_content: Optional[str] = None
    matched_pattern: Optional[str] = None
    agent_type: Optional[str] = None
    channel: Optional[str] = None
    user_id: Optional[str] = None
    action_taken: Optional[str] = None

    model_config = ConfigDict(
        json_encoders={datetime: lambda v: v.isoformat()},
    )


class SecurityGuardState(BaseModel):
    """Current state of security guard system."""

    total_rules: int = 0
    enabled_rules: int = 0
    violations_today: int = 0
    violations_total: int = 0
    last_violation_at: Optional[datetime] = None
