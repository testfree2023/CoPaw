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
from pathlib import Path
from typing import List, Callable, Any

logger = logging.getLogger(__name__)


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
                toolkit.register_tool_function(func)
                logger.debug(f"Registered tool: {func.__name__} from skill {skill_dir.name}")
                registered_count += 1
            except ValueError as e:
                # Tool already registered (normal in multi-agent scenarios)
                logger.debug(f"Tool already registered: {func.__name__} from {skill_dir.name} - {e}")
            except Exception as e:
                logger.warning(f"Failed to register tool {func.__name__} from {skill_dir.name}: {e}")

    return registered_count
