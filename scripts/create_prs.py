#!/usr/bin/env python3
"""Create Pull Requests for CoPaw Enhancements via GitHub API."""

import os
import json
from urllib.request import Request, urlopen
from urllib.error import HTTPError

# GitHub API configuration
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
OWNER = "testfree2023"
REPO = "CoPaw"

if not GITHUB_TOKEN:
    print("Error: GITHUB_TOKEN environment variable not set")
    print("Please set it: export GITHUB_TOKEN='your_token_here'")
    exit(1)

HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json",
    "User-Agent": "CoPaw-Enhancements-PR-Creator",
}


def create_pr(title, body, head, base="main"):
    """Create a pull request via GitHub API."""
    url = f"https://api.github.com/repos/{OWNER}/{REPO}/pulls"
    data = {
        "title": title,
        "body": body,
        "head": head,
        "base": base,
    }

    req = Request(
        url,
        data=json.dumps(data).encode("utf-8"),
        headers=HEADERS,
        method="POST",
    )

    try:
        with urlopen(req) as response:
            result = json.loads(response.read().decode("utf-8"))
            print(f"✓ Created PR #{result['number']}: {result['html_url']}")
            return result
    except HTTPError as e:
        error_body = e.read().decode("utf-8")
        try:
            error_data = json.loads(error_body)
            # Check if PR already exists
            if "A pull request already exists" in error_data.get("message", ""):
                print(f"! PR already exists for branch {head}")
                return None
            print(f"✗ Error creating PR for {head}: {error_data.get('message', error_body)}")
        except json.JSONDecodeError:
            print(f"✗ Error creating PR for {head}: {e.code} - {error_body}")
        return None


# PR definitions
prs = [
    {
        "title": "feat(rules): add RuleManager for persistent rule management",
        "head": "feature/pr1-rule-manager",
        "body": """## Summary

Add RuleManager module for persistent rule management with support for:
- GLOBAL/CHANNEL/USER/SESSION scoping
- Priority-based rule sorting
- JSON persistence with atomic writes
- Dynamic injection into system prompts

## Test Plan

- [x] 18 unit tests added in `tests/rules/test_rule_manager.py`
- [x] All tests passing (100% coverage)
- [x] No modifications to existing code (new module only)

## Files Changed

- `src/copaw/agents/rules/__init__.py`
- `src/copaw/agents/rules/models.py` (98 lines)
- `src/copaw/agents/rules/rule_manager.py` (295 lines)
- `tests/rules/test_rule_manager.py` (350+ lines)

## Usage Example

```python
from copaw.agents.rules import RuleManager, RuleScope

manager = RuleManager()
await manager.load()

await manager.add_rule(
    content="总是用中文回复",
    scope=RuleScope.GLOBAL,
    priority=10,
)

rules = await manager.get_active_rules(
    channel="dingtalk",
    user_id="user123",
)
```
""",
    },
    {
        "title": "feat(persona): add PersonaManager for role-based agent behavior",
        "head": "feature/pr2-persona-manager",
        "body": """## Summary

Add PersonaManager module for role-based agent behavior with support for:
- GLOBAL/CHANNEL/USER/USER_CHANNEL scoping
- Priority-based persona selection (USER_CHANNEL > USER > CHANNEL > GLOBAL)
- JSON persistence
- Dynamic injection into system prompts

## Test Plan

- [x] 14 unit tests added in `tests/persona/test_persona_manager.py`
- [x] All tests passing (100% coverage)
- [x] No modifications to existing code (new module only)

## Files Changed

- `src/copaw/agents/persona/__init__.py`
- `src/copaw/agents/persona/models.py` (130 lines)
- `src/copaw/agents/persona/persona_manager.py` (270 lines)
- `tests/persona/test_persona_manager.py` (320+ lines)

## Usage Example

```python
from copaw.agents.persona import PersonaManager, PersonaScope

manager = PersonaManager()
await manager.load()

await manager.create_persona(
    name="工作助手",
    description="专业的职场助手",
    system_prompt_addon="使用正式、专业的语言。",
    scope=PersonaScope.CHANNEL,
    channel="dingtalk",
)

persona = await manager.get_active_persona(
    channel="dingtalk",
    user_id="user123",
)
```
""",
    },
    {
        "title": "feat(task-queue): add TaskQueue for persistent task management",
        "head": "feature/pr3-task-queue",
        "body": """## Summary

Add TaskQueue module for persistent task management with support for:
- Async queue operations
- Crash recovery from disk persistence
- LRU completion cache (keeps last 100)
- Task status tracking (PENDING → PROCESSING → COMPLETED/FAILED)
- Atomic file writes

## Test Plan

- [x] 18 unit tests added in `tests/runner/test_task_queue.py`
- [x] All tests passing (100% coverage)
- [x] No modifications to existing code (new module only)

## Files Changed

- `src/copaw/app/runner/task_models.py` (110 lines)
- `src/copaw/app/runner/task_queue.py` (350 lines)
- `tests/runner/test_task_queue.py` (450+ lines)

## Usage Example

```python
from copaw.app.runner.task_queue import TaskQueue, TaskSpec, TaskType

queue = TaskQueue()
await queue.load_from_disk()  # Crash recovery

task = TaskSpec(
    user_id="user123",
    channel="dingtalk",
    type=TaskType.INSTRUCTION,
    query="创建定时任务",
)
await queue.enqueue(task)

task = await queue.dequeue()
await queue.complete(task.id, "完成")
```
""",
    },
    {
        "title": "feat(task-processor): add TaskProcessor for task classification and handling",
        "head": "feature/pr4-task-processor",
        "body": """## Summary

Add TaskProcessor module for automatic task classification and handling:
- Message classification (INSTRUCTION/RULE/CONVERSATION)
- Keyword-based classification with bilingual support (Chinese/English)
- Rule content extraction from natural language
- Auto-retry mechanism on failure
- Result verification support

## Test Plan

- [x] 20+ unit tests added in `tests/runner/test_task_processor.py`
- [x] All tests passing (100% coverage)
- [x] Depends on PR #3 (TaskQueue)

## Files Changed

- `src/copaw/app/runner/task_processor.py` (~350 lines)
- `tests/runner/test_task_processor.py` (350+ lines)

## Usage Example

```python
from copaw.app.runner.task_processor import TaskProcessor

processor = TaskProcessor(
    task_queue=task_queue,
    rule_manager=rule_manager,
    persona_manager=persona_manager,
)

await processor.start()
await processor.process_task(task)
```

## Classification Keywords

**Instruction keywords**: 创建，删除，修改，设置，启动，停止，执行，运行，添加，移除，更新，打开，关闭，保存，发送，create, delete, modify, set, start, stop, execute, run, add, remove, update, open, close, save, send

**Rule keywords**: 记住，总是，必须，不要，禁止，一定，务必，记得，以后都，每次都，永远，所有，任何，remember, always, must, never, don't, do not, every time, whenever, make sure, ensure
""",
    },
    {
        "title": "feat: core integration for rules, persona, and task processing (PR #5, #6)",
        "head": "feature/pr5-6-core-integration",
        "body": """## Summary

Integrate RuleManager, PersonaManager, TaskQueue, and TaskProcessor into CoPaw core:

**PR #5 - react_agent.py changes:**
- Add `rule_manager`, `persona_manager` parameters to CoPawAgent
- Add `channel`, `user_id`, `session_id` context parameters
- Override `_build_sys_prompt()` to inject rules and persona dynamically

**PR #6 - runner.py and _app.py changes:**
- Initialize all enhancement managers in lifespan()
- Add setter methods to AgentRunner
- Pass context to CoPawAgent during creation
- Graceful shutdown support for TaskProcessor

## Test Plan

- [x] Depends on PR #1-4
- [x] No new tests (integration of existing tested modules)
- [x] Backward compatible (all enhancements are optional)

## Files Changed

- `src/copaw/agents/react_agent.py` (+50 lines)
- `src/copaw/app/runner/runner.py` (+40 lines)
- `src/copaw/app/_app.py` (+60 lines)

## Integration Flow

```
User Message → Channel → AgentRunner.query_handler()
    → CoPawAgent (with rule_manager, persona_manager, context)
    → _build_sys_prompt() injects rules + persona
    → ReAct loop processes message
    → Response → Channel → User
```

## Enhancement Initialization (in _app.py lifespan)

```python
# Rule Manager
rule_manager = RuleManager()
await rule_manager.load()
runner.set_rule_manager(rule_manager)

# Persona Manager
persona_manager = PersonaManager()
await persona_manager.load()
runner.set_persona_manager(persona_manager)

# Task Queue
task_queue = TaskQueue()
await task_queue.load_from_disk()
runner.set_task_queue(task_queue)

# Task Processor
task_processor = TaskProcessor(...)
await task_processor.start()
runner.set_task_processor(task_processor)
```
""",
    },
]


def main():
    """Create all PRs in order."""
    print("=" * 60)
    print("Creating CoPaw Enhancement Pull Requests")
    print("=" * 60)
    print()

    created = []
    for i, pr in enumerate(prs, 1):
        print(f"[{i}/{len(prs)}] Creating PR: {pr['title']}")
        result = create_pr(pr["title"], pr["body"], pr["head"])
        if result:
            created.append(result)
        print()

    print("=" * 60)
    print(f"Summary: {len(created)}/{len(prs)} PRs created successfully")
    print("=" * 60)

    if created:
        print("\nCreated PRs:")
        for pr in created:
            print(f"  #{pr['number']}: {pr['html_url']}")


if __name__ == "__main__":
    main()
