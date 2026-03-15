# -*- coding: utf-8 -*-
"""Universal skill tool registration for CoPaw.

This module provides a mechanism to automatically scan skill directories
and register Python functions as toolkit tool functions.

The mechanism:
1. Scan active_skills directory for skills with __init__.py
2. Find exported async functions (not starting with _)
3. Register them as tool functions with the toolkit

Note: For skills with hyphens in directory name (e.g., stock-analysis-system),
a temporary symlink is created to enable proper Python package imports.
Skills should use consistent import styles:
- Either all relative imports (from .module import ...)
- Or all absolute imports with the skill as a package (from skill_name.module import ...)
"""
import os
import sys
import logging
import functools
import inspect
from pathlib import Path
from typing import List, Callable, Any, Optional

logger = logging.getLogger(__name__)


# Async context for skill function injection (per-task isolation)
# Using a task-local storage approach that survives async boundaries
import contextvars
import asyncio
from contextlib import contextmanager

# ContextVar approach (primary mechanism for async context propagation)
_skill_context_channel: contextvars.ContextVar[str | None] = contextvars.ContextVar("_skill_context_channel", default=None)
_skill_context_user_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("_skill_context_user_id", default=None)
_skill_context_session_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("_skill_context_session_id", default=None)

# Task-local fallback: store context by task id for reliable retrieval
# This ensures context survives even if ContextVar propagation fails
# Key is task id, value is context dict
_task_context_store: dict[int, dict] = {}

# Cleanup limit to prevent memory leaks
_MAX_TASK_CONTEXT_STORE_SIZE = 1000


def _cleanup_task_context():
    """Clean up old entries in task context store if it grows too large."""
    if len(_task_context_store) > _MAX_TASK_CONTEXT_STORE_SIZE:
        # Remove oldest entries (keep most recent 500)
        task_ids = list(_task_context_store.keys())
        for task_id in task_ids[:_MAX_TASK_CONTEXT_STORE_SIZE // 2]:
            del _task_context_store[task_id]


def set_skill_context(channel: str = None, user_id: str = None, session_id: str = None) -> None:
    """Set the current chat context for skill function calls.

    This is called by CoPawAgent before processing a user request,
    so that skill functions can access the current channel/user/session.

    Uses both ContextVar and task-local storage for maximum reliability.

    Args:
        channel: Current channel (console, dingtalk, feishu, etc.)
        user_id: Current user ID
        session_id: Current session ID
    """
    # Set ContextVar (for normal async propagation)
    _skill_context_channel.set(channel)
    _skill_context_user_id.set(user_id)
    _skill_context_session_id.set(session_id)

    # Also store in task-local dict (fallback for async boundary issues)
    task = asyncio.current_task()
    task_id = id(task) if task else 0
    _task_context_store[task_id] = {
        "channel": channel,
        "user_id": user_id,
        "session_id": session_id,
    }

    # Cleanup old entries periodically
    _cleanup_task_context()

    logger.info(
        f"[Skill Context] Set: channel={channel}, "
        f"user_id={(user_id or '')[:20]}, session_id={(session_id or '')[:20]}, "
        f"task_id={task_id}"
    )


def get_skill_context() -> dict:
    """Get the current skill context.

    Returns:
        dict with keys: channel, user_id, session_id
        Tries ContextVar first, then falls back to task-local storage
    """
    # Try ContextVar first
    ctx = {
        "channel": _skill_context_channel.get(),
        "user_id": _skill_context_user_id.get(),
        "session_id": _skill_context_session_id.get(),
    }

    # If ContextVar returns None values, try task-local storage
    if ctx["channel"] is None or ctx["user_id"] is None or ctx["session_id"] is None:
        task = asyncio.current_task()
        task_id = id(task) if task else 0
        task_ctx = _task_context_store.get(task_id, {})
        if task_ctx:
            logger.debug(f"[Skill Context] Using task-local fallback: {task_ctx}")
            ctx.update(task_ctx)

    return ctx


def inject_context_to_skill_function(func: Callable) -> Callable:
    """Wrap a skill function to inject context parameters.

    This wrapper adds context parameters to skill function calls:
    - context_channel: Current chat channel
    - context_user_id: Current user ID
    - context_session_id: Current session ID

    Args:
        func: The original skill function to wrap

    Returns:
        Wrapped function that injects context parameters
    """
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        # Get current context from ContextVar (set by agent's reply() method)
        # ContextVar should propagate through async calls within the same task
        context = get_skill_context()

        # Debug: log the context values to verify propagation
        logger.info(
            f"[Skill Context] {func.__name__} called - "
            f"ContextVar values: channel={context.get('channel')}, "
            f"user_id={(context.get('user_id') or '')[:20]}, "
            f"session_id={(context.get('session_id') or '')[:20]}"
        )

        # Only inject context if the function accepts these parameters
        sig = inspect.signature(func)
        params = sig.parameters

        # Check if function accepts context parameters (without leading underscore)
        if "context_channel" in params or "context_user_id" in params or "context_session_id" in params:
            # Inject context parameters
            if "context_channel" in params and "context_channel" not in kwargs:
                kwargs["context_channel"] = context.get("channel")
            if "context_user_id" in params and "context_user_id" not in kwargs:
                kwargs["context_user_id"] = context.get("user_id")
            if "context_session_id" in params and "context_session_id" not in kwargs:
                kwargs["context_session_id"] = context.get("session_id")
            logger.info(
                f"[Skill Context] Injecting context to {func.__name__}: "
                f"channel={kwargs.get('context_channel')}, "
                f"user_id={(kwargs.get('context_user_id') or '')[:20]}, "
                f"session_id={(kwargs.get('context_session_id') or '')[:20]}"
            )

        return await func(*args, **kwargs)

    return wrapper


def _get_skill_tool_functions(skill_dir: Path) -> List[Callable]:
    """Get all tool functions from a skill directory.

    This function handles skills with hyphens in directory names by creating
    a temporary symlink to enable proper Python package imports.

    Args:
        skill_dir: Path to the skill directory

    Returns:
        List of callable functions that can be registered as tools
    """
    init_file = skill_dir / "__init__.py"

    if not init_file.exists():
        logger.debug(f"Skill {skill_dir.name} has no __init__.py, skipping tool registration")
        return []

    try:
        import importlib

        # Convert skill dir name to valid Python identifier
        # e.g., stock-analysis-system -> stock_analysis_system
        module_name = skill_dir.name.replace("-", "_")

        # Create temporary symlink if directory name has hyphens
        temp_link = None
        if "-" in skill_dir.name:
            temp_link = skill_dir.parent / module_name
            if not temp_link.exists():
                os.symlink(skill_dir, temp_link)
                link_created = True
            else:
                link_created = False
        else:
            link_created = False

        # Add skill parent directory to sys.path
        skill_parent_dir = str(skill_dir.parent)
        path_added = False
        if skill_parent_dir not in sys.path:
            sys.path.insert(0, skill_parent_dir)
            path_added = True

        # Store old module state
        old_module = sys.modules.get(module_name)

        try:
            # Import the skill as a Python package
            module = importlib.import_module(module_name)
        except ImportError as e:
            logger.warning(f"Could not import skill {skill_dir.name}: {e}")
            return []
        except Exception as e:
            logger.warning(f"Could not load skill module {skill_dir.name}: {e}")
            return []
        finally:
            # Restore module state
            if old_module is None:
                sys.modules.pop(module_name, None)
            else:
                sys.modules[module_name] = old_module
            # Remove path if we added it
            if path_added and skill_parent_dir in sys.path:
                sys.path.remove(skill_parent_dir)
            # Remove temporary symlink
            if link_created and temp_link and temp_link.exists():
                try:
                    temp_link.unlink()
                except OSError:
                    pass

        # Find exported functions (not starting with _, and callable)
        tool_functions = []
        for name in dir(module):
            if name.startswith("_"):
                continue

            obj = getattr(module, name)
            if callable(obj):
                # Check if it's a function (not a class)
                import types
                if isinstance(obj, (types.FunctionType, type(lambda: None))):
                    tool_functions.append(obj)
                    logger.debug(f"Found tool function: {name} in skill {skill_dir.name}")

        return tool_functions

    except Exception as e:
        logger.warning(f"Failed to load tools from skill {skill_dir.name}: {e}")
        return []


def register_skill_tools(toolkit: Any, active_skills_dir: Path) -> int:
    """Register all skill tools from active_skills directory.

    This scans all skill directories and registers exported functions
    as tool functions in the toolkit.

    Args:
        toolkit: The Toolkit instance to register tools to
        active_skills_dir: Path to the active_skills directory

    Returns:
        Number of tools registered
    """
    if not active_skills_dir.exists():
        logger.debug(f"Active skills directory does not exist: {active_skills_dir}")
        return 0

    registered_count = 0

    for skill_dir in active_skills_dir.iterdir():
        if not skill_dir.is_dir():
            continue

        # Check if skill has __init__.py (Python module)
        if not (skill_dir / "__init__.py").exists():
            continue

        # Get tool functions from this skill
        tool_functions = _get_skill_tool_functions(skill_dir)

        # Register each function as a tool
        for func in tool_functions:
            try:
                # Wrap function to inject context if it accepts context parameters
                wrapped_func = inject_context_to_skill_function(func)
                toolkit.register_tool_function(wrapped_func)
                logger.debug(f"Registered tool: {func.__name__} from skill {skill_dir.name}")
                registered_count += 1
            except ValueError as e:
                # Tool already registered (normal in multi-agent scenarios)
                logger.debug(f"Tool already registered: {func.__name__} from {skill_dir.name} - {e}")
            except Exception as e:
                logger.warning(f"Failed to register tool {func.__name__} from {skill_dir.name}: {e}")

    return registered_count
