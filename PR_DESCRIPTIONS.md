# CoPaw Enhancements - PR 描述模板

## PR #1: RuleManager 规则管理

**标题**: `feat(rules): add RuleManager for persistent rule management`

**描述**:
```markdown
## Summary
添加规则管理模块，支持用户定义持久化规则来指导 Agent 行为。

## Features
- RuleSpec 模型支持 GLOBAL/CHANNEL/USER/SESSION 四种作用域
- RuleManager 提供完整的 CRUD 操作
- 基于优先级的规则排序
- JSON 持久化存储（原子写入）
- 完整的单元测试覆盖（18 个测试用例）

## Usage
```python
from copaw.agents.rules import RuleManager, RuleScope

manager = RuleManager()
await manager.add_rule(
    content="总是用中文回复",
    scope=RuleScope.GLOBAL,
    priority=10,
)
```

## Testing
- 运行测试：`pytest tests/rules/test_rule_manager.py -v`
- 测试覆盖率：100% (18/18)

## Backward Compatibility
- 不修改现有代码
- 新模块为可选功能
- 完全向后兼容
```

---

## PR #2: PersonaManager 角色管理

**标题**: `feat(persona): add PersonaManager for role-based agent behavior`

**描述**:
```markdown
## Summary
添加角色管理模块，支持为不同渠道/用户定义不同的 Agent 角色。

## Features
- PersonaSpec 模型支持 GLOBAL/CHANNEL/USER/USER_CHANNEL 四种作用域
- PersonaManager 提供完整的 CRUD 操作
- 优先级选择机制（USER_CHANNEL > USER > CHANNEL > GLOBAL）
- JSON 持久化存储
- 完整的单元测试覆盖（14 个测试用例）

## Usage
```python
from copaw.agents.persona import PersonaManager, PersonaScope

manager = PersonaManager()
await manager.create_persona(
    name="工作助手",
    description="专业的职场助手",
    system_prompt_addon="使用正式、专业的语言。",
    scope=PersonaScope.CHANNEL,
    channel="dingtalk",
)
```

## Testing
- 运行测试：`pytest tests/persona/test_persona_manager.py -v`
- 测试覆盖率：100% (14/14)

## Backward Compatibility
- 不修改现有代码
- 新模块为可选功能
- 完全向后兼容
```

---

## PR #3: TaskQueue 持久化队列

**标题**: `feat(task-queue): add TaskQueue for persistent task management`

**描述**:
```markdown
## Summary
添加持久化任务队列，支持任务生命周期追踪和崩溃恢复。

## Features
- TaskSpec 模型追踪任务状态（PENDING/PROCESSING/COMPLETED/FAILED）
- TaskQueue 提供异步入队/出队操作
- 崩溃恢复功能（从磁盘重新加载 pending/processing 任务）
- LRU 完成缓存（保留最后 100 个任务）
- 原子文件写入
- 完整的单元测试覆盖（18 个测试用例）

## Usage
```python
from copaw.app.runner.task_queue import TaskQueue, TaskSpec, TaskType

queue = TaskQueue()
await queue.load_from_disk()

task = TaskSpec(
    user_id="user123",
    channel="dingtalk",
    type=TaskType.INSTRUCTION,
    query="创建定时任务",
)
await queue.enqueue(task)
```

## Testing
- 运行测试：`pytest tests/runner/test_task_queue.py -v`
- 测试覆盖率：100% (18/18)

## Backward Compatibility
- 不修改现有代码
- 新模块为可选功能
- 完全向后兼容
```

---

## 合并顺序

建议按以下顺序合并 PR：
1. PR #1: RuleManager (基础功能)
2. PR #2: PersonaManager (基础功能)
3. PR #3: TaskQueue (基础功能)
4. PR #4: TaskProcessor (依赖 PR #3)
5. PR #5: 核心集成 (依赖 PR #1-4)
6. PR #6: 核心集成 (依赖 PR #5)

---

**创建时间**: 2026-03-02
