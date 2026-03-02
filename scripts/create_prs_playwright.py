#!/usr/bin/env python3
"""Create Pull Requests for CoPaw Enhancements via Playwright.

This script automates the creation of PRs using browser automation.
It will open GitHub pages and fill in the PR forms automatically.

Usage:
    python scripts/create_prs_playwright.py

Note: You need to be logged in to GitHub in your browser, or the script
will prompt you to log in manually.
"""

import asyncio
from playwright.async_api import async_playwright, Page, Browser

# PR definitions
PRS = [
    {
        "title": "feat(rules): add RuleManager for persistent rule management",
        "branch": "feature/pr1-rule-manager",
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
```
""",
    },
    {
        "title": "feat(persona): add PersonaManager for role-based agent behavior",
        "branch": "feature/pr2-persona-manager",
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
```
""",
    },
    {
        "title": "feat(task-queue): add TaskQueue for persistent task management",
        "branch": "feature/pr3-task-queue",
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
        "branch": "feature/pr4-task-processor",
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
""",
    },
    {
        "title": "feat: core integration for rules, persona, and task processing (PR #5, #6)",
        "branch": "feature/pr5-6-core-integration",
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
""",
    },
]

OWNER = "testfree2023"
REPO = "CoPaw"


async def create_pr(page: Page, pr: dict, pr_number: int, total: int) -> str:
    """Create a single PR and return the URL if successful."""
    url = f"https://github.com/{OWNER}/{REPO}/compare/{pr['branch']}?expand=1"

    print(f"\n[{pr_number}/{total}] Creating PR: {pr['title']}")
    print(f"    URL: {url}")

    try:
        # Navigate to the compare page
        await page.goto(url, timeout=60000)
        await page.wait_for_timeout(3000)  # Wait for page to load

        # Check if we need to log in
        if "login" in page.url.lower():
            print("    ⚠️  GitHub login required. Please log in manually...")
            # Wait for user to log in
            await page.wait_for_function(
                "document.querySelector('img.avatar') !== null",
                timeout=300000  # 5 minutes timeout
            )
            await page.wait_for_timeout(2000)

        # Check if PR already exists
        existing_pr_indicator = await page.query_selector('[data-testid="state-label"]')
        if existing_pr_indicator:
            state = await existing_pr_indicator.inner_text()
            print(f"    ⚠️  PR already exists: {state}")
            return "exists"

        # Check if compare shows "no changes"
        no_changes = await page.query_selector('text="There isn\'t anything to compare"')
        if no_changes:
            print(f"    ⚠️  No changes to compare for branch {pr['branch']}")
            return "no-changes"

        # Fill in the title
        title_selector = 'input[id="pull_request_title"]'
        title_element = await page.query_selector(title_selector)
        if title_element:
            await title_element.fill(pr['title'])
            await page.wait_for_timeout(500)
        else:
            print("    ⚠️  Could not find title field")

        # Fill in the body using JavaScript to ensure it works
        body_text = pr['body']
        await page.evaluate(f"""
            (() => {{
                const textarea = document.querySelector('textarea[id="pull_request_body"]');
                if (textarea) {{
                    textarea.value = `{body_text.replace('`', '\\`').replace('$', '\\$')}`;
                    textarea.dispatchEvent(new Event('input', {{ bubbles: true }}));
                }}
            }})()
        """)
        await page.wait_for_timeout(500)

        # Try alternative method to fill body
        body_selector = 'textarea[id="pull_request_body"]'
        body_element = await page.query_selector(body_selector)
        if body_element:
            await body_element.fill(body_text)
            await page.wait_for_timeout(500)

        # Click the create PR button
        create_button = await page.query_selector('button[id="submit-button"]')
        if create_button:
            await create_button.click()
            print("    ✓  Clicked create PR button")

            # Wait for navigation to the new PR
            await page.wait_for_navigation(timeout=30000)
            await page.wait_for_timeout(2000)

            # Get the PR URL
            pr_url = page.url
            if "/pull/" in pr_url:
                print(f"    ✓  Created: {pr_url}")
                return pr_url
            else:
                print(f"    ⚠️  Navigation may not have completed. Current URL: {pr_url}")
                return pr_url
        else:
            print("    ⚠️  Could not find create PR button")
            # Check for error messages
            error = await page.query_selector('.flash-error')
            if error:
                print(f"    ✗  Error: {await error.inner_text()}")
            return "error"

    except Exception as e:
        print(f"    ✗  Error: {str(e)}")
        return f"error: {str(e)}"


async def main():
    """Main function to create all PRs."""
    print("=" * 70)
    print("CoPaw Enhancements - Pull Request Creator (Playwright)")
    print("=" * 70)
    print(f"\nRepository: {OWNER}/{REPO}")
    print(f"Total PRs to create: {len(PRS)}")
    print("\nNote: Please ensure you are logged in to GitHub.")
    print("If not logged in, you will have 5 minutes to log in manually.")

    async with async_playwright() as p:
        # Launch browser
        browser: Browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800}
        )
        page = await context.new_page()

        # Go to GitHub first to check login status
        print("\nOpening GitHub to check login status...")
        await page.goto("https://github.com", timeout=60000)
        await page.wait_for_timeout(3000)

        # Check if logged in
        avatar = await page.query_selector('img.avatar')
        if not avatar:
            print("⚠️  Not logged in to GitHub. Please log in...")
            print("   (You have 5 minutes)")
            try:
                await page.wait_for_function(
                    "document.querySelector('img.avatar') !== null",
                    timeout=300000
                )
                print("✓  Logged in successfully")
            except Exception:
                print("✗  Login timeout. Exiting.")
                await browser.close()
                return

        # Create PRs
        results = []
        for i, pr in enumerate(PRS, 1):
            result = await create_pr(page, pr, i, len(PRS))
            results.append((pr['branch'], result))
            await page.wait_for_timeout(3000)  # Wait between PRs

        await browser.close()

        # Print summary
        print("\n" + "=" * 70)
        print("Summary")
        print("=" * 70)
        for branch, result in results:
            status = "✓" if result.startswith("http") else "⚠️" if result in ["exists", "no-changes"] else "✗"
            print(f"{status} {branch}: {result}")


if __name__ == "__main__":
    asyncio.run(main())
