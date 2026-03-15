# -*- coding: utf-8 -*-
"""Security Guard Manager for CoPaw.

This module provides the SecurityGuardManager class for loading, managing,
and enforcing security guard rules.
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .models import (
    RuleCategory,
    RuleScope,
    RuleSeverity,
    RuleViolationRecord,
    SecurityGuardConfig,
    SecurityGuardRule,
    SecurityGuardRuleSpec,
    SecurityGuardState,
)

logger = logging.getLogger(__name__)

# Default path for security guard configuration
DEFAULT_SECURITY_GUARD_PATH = Path.home() / ".copaw" / "security_guard.json"
DEFAULT_RULES_DIR = Path(__file__).parent / "rules"


class SecurityGuardManager:
    """Manages security guard rules for CoPaw.

    This manager handles:
    - Loading rules from configuration file
    - Loading default rules from package
    - Runtime rule management (add, update, delete, enable, disable)
    - Rule enforcement and violation detection
    - Violation logging and tracking
    """

    def __init__(
        self,
        config_path: Optional[Path] = None,
        rules_dir: Optional[Path] = None,
    ):
        """Initialize security guard manager.

        Args:
            config_path: Path to security guard config file
            rules_dir: Path to directory with default rule files
        """
        self._config_path = config_path or DEFAULT_SECURITY_GUARD_PATH
        self._rules_dir = rules_dir or DEFAULT_RULES_DIR
        self._config: Optional[SecurityGuardConfig] = None
        self._violations: List[RuleViolationRecord] = []

    async def load(self) -> None:
        """Load security guard configuration from file and defaults.

        Loads in order:
        1. Default rules from package (if not already present)
        2. User configuration from config file
        """
        logger.info("Loading security guard configuration")

        # Start with default config
        self._config = SecurityGuardConfig()

        # Load default rules from package
        await self._load_default_rules()

        # Load user config (overrides defaults)
        await self._load_user_config()

        logger.info(
            "Security guard loaded: %d total rules, %d enabled",
            len(self._config.rules),
            len(self._config.get_enabled_rules()),
        )

    async def _load_default_rules(self) -> None:
        """Load default rules from package."""
        # Try to load rules from .md files in rules directory
        if not self._rules_dir.exists():
            logger.debug("Default rules directory not found, skipping")
            return

        for rule_file in self._rules_dir.glob("*.md"):
            try:
                rule = await self._parse_rule_file(rule_file)
                if rule:
                    # Check if rule already exists
                    existing = next(
                        (r for r in self._config.rules if r.id == rule.id), None
                    )
                    if not existing:
                        self._config.rules.append(rule)
                        logger.debug(f"Loaded default rule: {rule.name}")
            except Exception as e:
                logger.warning(f"Failed to load rule from {rule_file}: {e}")

    async def _parse_rule_file(self, file_path: Path) -> Optional[SecurityGuardRule]:
        """Parse a rule from a markdown file.

        Expected format:
        ---
        id: rule-001
        name: No Harmful Content
        category: content_safety
        severity: critical
        ---

        # Description
        Detailed description...

        ## Patterns
        - pattern1
        - pattern2
        """
        content = file_path.read_text(encoding="utf-8")

        # Try to extract YAML front matter
        if not content.startswith("---"):
            return None

        parts = content.split("---", 2)
        if len(parts) < 3:
            return None

        yaml_content = parts[1].strip()
        markdown_content = parts[2].strip()

        # Parse YAML (simple parser, not full YAML)
        metadata: Dict[str, Any] = {}
        for line in yaml_content.split("\n"):
            if ":" in line:
                key, value = line.split(":", 1)
                key = key.strip()
                value = value.strip().strip('"\'')
                if value:
                    metadata[key] = value

        # Parse patterns from markdown
        patterns = []
        in_patterns = False
        for line in markdown_content.split("\n"):
            if "## Patterns" in line or "## 模式" in line:
                in_patterns = True
                continue
            if in_patterns:
                if line.startswith("## "):
                    in_patterns = False
                elif line.strip().startswith("- "):
                    patterns.append(line.strip()[2:])

        if "id" not in metadata:
            return None

        return SecurityGuardRule(
            id=metadata.get("id", str(uuid.uuid4())),
            name=metadata.get("name", "Unnamed Rule"),
            description=markdown_content.split("\n")[0].strip() if markdown_content else "",
            category=RuleCategory(metadata.get("category", "custom")),
            severity=RuleSeverity(metadata.get("severity", "medium")),
            scope=RuleScope(metadata.get("scope", "global")),
            patterns=patterns,
            enabled=True,
        )

    async def _load_user_config(self) -> None:
        """Load user configuration from file."""
        if not self._config_path.exists():
            logger.debug("User config not found, using defaults")
            return

        try:
            data = json.loads(self._config_path.read_text(encoding="utf-8"))

            # Merge with current config
            if "enabled" in data:
                self._config.enabled = data["enabled"]
            if "log_violations" in data:
                self._config.log_violations = data["log_violations"]

            # Load or merge rules
            if "rules" in data:
                user_rules = data["rules"]
                for rule_data in user_rules:
                    rule_id = rule_data.get("id")
                    if not rule_id:
                        continue

                    # Check if updating existing rule
                    existing_idx = next(
                        (i for i, r in enumerate(self._config.rules) if r.id == rule_id),
                        None,
                    )

                    if existing_idx is not None:
                        # Update existing rule
                        existing_rule = self._config.rules[existing_idx]
                        for key, value in rule_data.items():
                            if hasattr(existing_rule, key) and key != "id":
                                setattr(existing_rule, key, value)
                        existing_rule.updated_at = datetime.now()
                    else:
                        # Add new rule
                        new_rule = SecurityGuardRule(
                            id=rule_id,
                            name=rule_data.get("name", "Custom Rule"),
                            description=rule_data.get("description", ""),
                            category=RuleCategory(rule_data.get("category", "custom")),
                            severity=RuleSeverity(rule_data.get("severity", "medium")),
                            scope=RuleScope(rule_data.get("scope", "global")),
                            patterns=rule_data.get("patterns", []),
                            blocked_actions=rule_data.get("blocked_actions", []),
                            enabled=rule_data.get("enabled", True),
                            target_agents=rule_data.get("target_agents"),
                            target_channels=rule_data.get("target_channels"),
                            target_users=rule_data.get("target_users"),
                        )
                        self._config.rules.append(new_rule)

            logger.info(f"Loaded user security guard config from {self._config_path}")
        except Exception as e:
            logger.warning(f"Failed to load user config: {e}")

    async def save(self) -> None:
        """Save current configuration to file."""
        self._config_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "version": self._config.version,
            "enabled": self._config.enabled,
            "log_violations": self._config.log_violations,
            "notify_on_violation": self._config.notify_on_violation,
            "rules": [r.model_dump(mode="json") for r in self._config.rules],
        }

        # Atomic write
        tmp_path = self._config_path.with_suffix(".tmp")
        tmp_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        tmp_path.replace(self._config_path)

        logger.info(f"Saved security guard config to {self._config_path}")

    def get_config(self) -> SecurityGuardConfig:
        """Get current configuration."""
        if self._config is None:
            raise RuntimeError("SecurityGuardManager not loaded")
        return self._config

    def get_state(self) -> SecurityGuardState:
        """Get current system state."""
        if self._config is None:
            return SecurityGuardState()

        now = datetime.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        today_violations = sum(
            1 for v in self._violations if v.triggered_at >= today_start
        )

        last_violation = None
        if self._violations:
            last_violation = max(v.triggered_at for v in self._violations)

        return SecurityGuardState(
            total_rules=len(self._config.rules),
            enabled_rules=len(self._config.get_enabled_rules()),
            violations_today=today_violations,
            violations_total=len(self._violations),
            last_violation_at=last_violation,
        )

    async def add_rule(self, spec: SecurityGuardRuleSpec) -> SecurityGuardRule:
        """Add a new rule.

        Args:
            spec: Rule specification

        Returns:
            Created rule
        """
        rule = SecurityGuardRule(
            id=str(uuid.uuid4()),
            name=spec.name,
            description=spec.description,
            category=spec.category,
            severity=spec.severity,
            scope=spec.scope,
            patterns=spec.patterns,
            blocked_actions=spec.blocked_actions,
            enabled=spec.enabled,
            target_agents=spec.target_agents,
            target_channels=spec.target_channels,
            target_users=spec.target_users,
        )

        if self._config is None:
            self._config = SecurityGuardConfig()

        self._config.rules.append(rule)
        await self.save()

        logger.info(f"Added security rule: {rule.name} ({rule.id})")
        return rule

    async def update_rule(
        self, rule_id: str, updates: Dict[str, Any]
    ) -> Optional[SecurityGuardRule]:
        """Update an existing rule.

        Args:
            rule_id: ID of rule to update
            updates: Fields to update

        Returns:
            Updated rule or None if not found
        """
        if self._config is None:
            return None

        rule = next((r for r in self._config.rules if r.id == rule_id), None)
        if rule is None:
            return None

        for key, value in updates.items():
            if hasattr(rule, key) and key not in ("id", "created_at"):
                setattr(rule, key, value)

        rule.updated_at = datetime.now()
        await self.save()

        logger.info(f"Updated security rule: {rule.name} ({rule_id})")
        return rule

    async def delete_rule(self, rule_id: str) -> bool:
        """Delete a rule.

        Args:
            rule_id: ID of rule to delete

        Returns:
            True if deleted, False if not found
        """
        if self._config is None:
            return False

        before = len(self._config.rules)
        self._config.rules = [r for r in self._config.rules if r.id != rule_id]

        if len(self._config.rules) < before:
            await self.save()
            logger.info(f"Deleted security rule: {rule_id}")
            return True

        return False

    async def enable_rule(self, rule_id: str) -> bool:
        """Enable a rule."""
        return await self.update_rule(rule_id, {"enabled": True})

    async def disable_rule(self, rule_id: str) -> bool:
        """Disable a rule."""
        return await self.update_rule(rule_id, {"enabled": False})

    def check_input(
        self,
        input_text: str,
        agent_type: Optional[str] = None,
        channel: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Tuple[bool, Optional[SecurityGuardRule], Optional[str]]:
        """Check if input violates any security rules.

        Args:
            input_text: User input to check
            agent_type: Type of agent processing
            channel: Channel where input came from
            user_id: User who sent input

        Returns:
            Tuple of (is_safe, violated_rule, matched_pattern)
            If safe: (True, None, None)
            If violation: (False, rule, pattern)
        """
        if self._config is None or not self._config.enabled:
            return (True, None, None)

        rules = self._config.get_enabled_rules()

        for rule in rules:
            # Check scope filters
            if not self._rule_applies(rule, agent_type, channel, user_id):
                continue

            # Check patterns
            matched_pattern = self._match_patterns(input_text, rule.patterns)
            if matched_pattern:
                # Record violation
                self._record_violation(
                    rule=rule,
                    input_content=input_text,
                    matched_pattern=matched_pattern,
                    agent_type=agent_type,
                    channel=channel,
                    user_id=user_id,
                )

                return (False, rule, matched_pattern)

        return (True, None, None)

    def _rule_applies(
        self,
        rule: SecurityGuardRule,
        agent_type: Optional[str],
        channel: Optional[str],
        user_id: Optional[str],
    ) -> bool:
        """Check if rule applies to given context."""
        # Check scope
        if rule.scope == RuleScope.GLOBAL:
            return True

        if rule.scope == RuleScope.AGENT and rule.target_agents:
            if agent_type not in rule.target_agents:
                return False

        if rule.scope == RuleScope.CHANNEL and rule.target_channels:
            if channel not in rule.target_channels:
                return False

        if rule.scope == RuleScope.USER and rule.target_users:
            if user_id not in rule.target_users:
                return False

        return True

    def _match_patterns(self, text: str, patterns: List[str]) -> Optional[str]:
        """Check if text matches any patterns.

        Args:
            text: Text to check
            patterns: List of patterns (keywords or regex)

        Returns:
            Matched pattern or None
        """
        text_lower = text.lower()

        for pattern in patterns:
            pattern_lower = pattern.lower()

            # Try as regex first
            if pattern.startswith("/") and pattern.endswith("/"):
                try:
                    regex = pattern[1:-1]
                    if re.search(regex, text, re.IGNORECASE):
                        return pattern
                except re.error:
                    pass
            # Check as keyword/phrase
            elif pattern_lower in text_lower:
                return pattern

        return None

    def _record_violation(
        self,
        rule: SecurityGuardRule,
        input_content: str,
        matched_pattern: str,
        agent_type: Optional[str],
        channel: Optional[str],
        user_id: Optional[str],
    ) -> None:
        """Record a rule violation."""
        violation = RuleViolationRecord(
            id=str(uuid.uuid4()),
            rule_id=rule.id,
            rule_name=rule.name,
            triggered_at=datetime.now(),
            input_content=input_content[:500] if len(input_content) > 500 else input_content,
            matched_pattern=matched_pattern,
            agent_type=agent_type,
            channel=channel,
            user_id=user_id,
            action_taken="blocked",
        )

        self._violations.append(violation)

        if self._config and self._config.log_violations:
            logger.warning(
                f"Security rule violated: {rule.name} | "
                f"Pattern: {matched_pattern} | "
                f"User: {user_id} | "
                f"Channel: {channel}"
            )

    def get_violations(
        self,
        limit: int = 100,
        rule_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> List[RuleViolationRecord]:
        """Get violation records.

        Args:
            limit: Max records to return
            rule_id: Filter by rule
            user_id: Filter by user

        Returns:
            List of violations, newest first
        """
        violations = self._violations

        if rule_id:
            violations = [v for v in violations if v.rule_id == rule_id]
        if user_id:
            violations = [v for v in violations if v.user_id == user_id]

        # Sort by time descending
        sorted_violations = sorted(
            violations, key=lambda v: v.triggered_at, reverse=True
        )

        return sorted_violations[:limit]

    def get_rules_text(self) -> str:
        """Get enabled rules as text for system prompt injection.

        Returns:
            Formatted text describing active security rules
        """
        if self._config is None or not self._config.enabled:
            return ""

        rules = self._config.get_enabled_rules()
        if not rules:
            return ""

        text_parts = [
            "\n\n# 安全守卫规则 (Security Guard Rules)",
            "你必须遵守以下安全规则：\n"
        ]

        for rule in rules:
            if rule.description:
                text_parts.append(f"- **{rule.name}**: {rule.description}")

        text_parts.append(
            "\n如果用户请求违反上述任何规则，你必须拒绝执行并简要说明原因。"
        )

        return "\n".join(text_parts)
