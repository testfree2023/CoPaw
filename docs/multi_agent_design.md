# 多智能体架构设计方案

## 1. 架构概述

### 1.1 核心概念

```
┌─────────────────────────────────────────────────────────────────┐
│                        CoPaw 主智能体 (PM)                        │
│                    角色：管家/协调员/Dispatcher                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │              AgentRouter (智能体路由器)                     │  │
│  │  - 分析用户消息意图                                          │  │
│  │  - 根据 Persona 配置匹配最佳智能体                            │  │
│  │  - 支持 scope 规则：GLOBAL/CHANNEL/USER/USER_CHANNEL        │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│ 教师智能体     │    │ 技术专家智能体  │    │ 投资专家智能体  │
│ (Teacher)     │    │ (TechExpert)  │    │ (Investor)    │
├───────────────┤    ├───────────────┤    ├───────────────┤
│ scope: user   │    │ scope: user   │    │ scope: user   │
│ user_ids: [...]│   │ user_ids: [...]│   │ user_ids: [...]│
└───────────────┘    └───────────────┘    └───────────────┘
```

### 1.2 与当前 Persona 系统的关系

**当前实现**：Persona 是系统提示词附加内容（`system_prompt_addon`）
**多智能体实现**：Persona 升级为 AgentInstance 配置，包含：
- 原有的 name, description, scope, channel, user_ids
- 新增：agent_type（引用的智能体类型）、model_config（独立模型配置）

### 1.3 设计目标

1. **真正的主智能体（PM）角色**：主智能体作为管家，负责任务分发和协调
2. **独立智能体实例**：每个专家智能体有独立的系统提示词和模型配置
3. **动态路由**：根据用户/频道/消息内容自动路由到最合适的智能体
4. **向后兼容**：保留 Persona 系统作为简单场景的轻量级方案

## 2. 核心组件设计

### 2.1 AgentInstance（智能体实例）

```python
class AgentInstance(BaseModel):
    """一个可被路由的智能体实例配置"""
    id: str
    name: str  # 如 "中学优秀教师"
    description: str
    agent_type: str  # 智能体类型，如 "teacher", "expert", "investor"

    # Scope 配置（复用 Persona 的 scope 系统）
    scope: AgentScope  # GLOBAL, CHANNEL, USER, USER_CHANNEL
    channel: Optional[str] = None
    user_ids: Optional[str] = None  # 空格分隔

    # 模型配置（可选，覆盖全局配置）
    model_name: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None

    # 系统提示词（完整提示词，不是 addon）
    system_prompt: str

    # 状态
    enabled: bool = True
```

### 2.2 AgentRouter（智能体路由器）

```python
class AgentRouter:
    """
    智能体路由器 - 负责根据消息上下文选择最佳智能体
    """

    async def route_request(
        self,
        channel: str,
        user_id: str,
        session_id: str,
        message: str,
    ) -> AgentInstance:
        """
        根据 channel, user_id 和消息内容选择最合适的智能体

        优先级：USER_CHANNEL > USER > CHANNEL > GLOBAL
        如果多个匹配，使用优先级最高的
        """
```

### 2.3 AgentInstanceManager（智能体实例管理器）

```python
class AgentInstanceManager:
    """
    管理所有智能体实例的生命周期
    - 加载/保存配置
    - 缓存已创建的 Agent 实例
    - 懒加载：首次请求时创建
    """

    async def get_or_create_agent(self, instance_id: str) -> CoPawAgent:
        """获取或创建智能体实例"""

    async def invalidate_cache(self, instance_id: str):
        """使缓存失效（配置更新时）"""
```

### 2.4 升级后的 CoPawAgent（主智能体）

```python
class CoPawAgent(ReActAgent):
    """
    主智能体 - 扮演 PM/管家角色
    - 处理通用对话
    - 当消息匹配到特定智能体时，路由到该智能体
    - 保持元认知：知道何时应该交给专家处理
    """

    def __init__(self):
        self._agent_router: AgentRouter = None
        self._agent_instance_manager: AgentInstanceManager = None

    async def reply(self, msg: Msg | list[Msg] | None = None, ...) -> Msg:
        # 1. 检查是否匹配特定智能体
        matched_agent = await self._agent_router.route_request(...)

        if matched_agent and matched_agent.id != self.id:
            # 2. 路由到匹配的智能体
            return await self._agent_instance_manager.process_with_agent(
                matched_agent.id, msg
            )

        # 3. 默认：主智能体处理（PM 角色）
        return await super().reply(msg)
```

## 3. 数据流

### 3.1 消息处理流程

```
用户消息 (钉钉/飞书等)
    │
    ▼
Channel 接收
    │
    ▼
AgentRequest
    │
    ▼
┌─────────────────────────────────────┐
│ CoPawAgent (主智能体/PM)             │
│ 1. 调用 AgentRouter.route_request() │
│ 2. 判断是否匹配特定智能体             │
└─────────────────────────────────────┘
    │
    ├─► 匹配到专家智能体 ──► AgentInstanceManager.get_or_create()
    │                        │
    │                        ▼
    │                     专家智能体处理
    │                        │
    │                        ▼
    │                     AgentResponse
    │
    └─► 无匹配 ──► 主智能体处理 (通用助手)
                 │
                 ▼
              AgentResponse
    │
    ▼
Channel 发送回复
```

### 3.2 配置管理流程

```
用户在前端创建/编辑智能体
    │
    ▼
POST/PUT /api/agent-instances
    │
    ▼
AgentInstanceManager
    │
    ├─► 保存到 JSON 文件 (~/.copaw/agent_instances.json)
    │
    └─► 使缓存失效
        │
        ▼
    下次请求时重新加载
```

## 4. API 设计

### 4.1 智能体实例管理 API

```
GET    /api/agent-instances          # 列出所有智能体实例
POST   /api/agent-instances          # 创建智能体实例
GET    /api/agent-instances/{id}     # 获取单个智能体
PUT    /api/agent-instances/{id}     # 更新智能体
DELETE /api/agent-instances/{id}     # 删除智能体
POST   /api/agent-instances/{id}/toggle  # 切换启用状态
```

### 4.2 路由测试 API

```
POST /api/agent-instances/test-route
Body: { "channel": "dingtalk", "user_id": "xxx", "message": "..." }
Response: { "matched_agent": {...}, "reason": "..." }
```

## 5. 前端页面

### 5.1 菜单结构调整

将 "Personas" 改名为 "智能体实例" (Agent Instances)，移动到 "智能体" 分组：

```
智能体 (Agent) 分组:
  - 工作区 (workspace)
  - 技能 (skills)
  - MCP
  - 运行配置 (agent-config)
  - 智能体实例 (agent-instances)  <-- 新增，原 personas 位置
```

### 5.2 智能体实例页面字段

| 字段 | 类型 | 说明 |
|------|------|------|
| 名称 | string | 智能体显示名称 |
| 描述 | string | 智能体描述 |
| 智能体类型 | select | teacher/expert/investor/custom |
| 系统提示词 | textarea | 完整的系统提示词 |
| 作用域 | select | GLOBAL/CHANNEL/USER/USER_CHANNEL |
| 频道 | string | 当作用域为 CHANNEL/USER_CHANNEL 时必填 |
| 用户 ID 列表 | string | 空格分隔，当作用域为 USER/USER_CHANNEL 时必填 |
| 模型配置 | object | 可选，覆盖全局模型配置 |
| 启用状态 | switch | 是否启用 |

## 6. 测试策略

### 6.1 单元测试

- `test_agent_router.py`: 测试路由逻辑
- `test_agent_instance_manager.py`: 测试实例管理
- `test_multi_agent_dispatch.py`: 测试多智能体分发

### 6.2 集成测试

- 创建多个智能体实例
- 模拟不同 channel/user 的消息
- 验证消息被正确的智能体处理

### 6.3 E2E 测试

- 前端创建智能体
- 通过 API 发送消息
- 验证回复符合预期智能体角色

## 7. 实现优先级

### Phase 1: 基础架构
1. 创建 `AgentInstance` 模型
2. 创建 `AgentInstanceManager`
3. 创建 `AgentRouter`
4. API 端点

### Phase 2: 集成
5. 修改主智能体使用路由
6. 前端页面调整（Personas -> Agent Instances）

### Phase 3: 完善
7. 测试用例
8. 文档更新
9. 性能优化（缓存策略）

## 11. 实现状态 (2026-03-03)

### Phase 1: 基础架构 - 已完成 ✅

- [x] 创建 `AgentInstance` 模型
- [x] 创建 `AgentInstanceManager`
- [x] 创建 `AgentRouter`
- [x] API 端点 (`/api/agent-instances`)

### Phase 2: 主智能体路由功能 - 已完成 ✅

- [x] 修改 `CoPawAgent.reply()` 方法，添加路由逻辑
- [x] 实现 `AgentInstanceManager.get_or_create_agent()` 懒加载
- [x] 添加专家智能体缓存机制
- [x] 编写单元测试 (18 个测试用例)

### Phase 3: 前端整合 - 已完成 ✅

- [x] 前端菜单调整：Personas -> 智能体实例（移动到 Agent 分组）
- [x] 添加路由重定向 (/personas -> /agent-instances)
- [x] Agent Instances 页面功能完整

### Phase 4: 测试完善 - 已完成 ✅

- [x] 单元测试 (`test_multi_agent_routing.py` - 18 个测试)
  - 实例创建/更新/删除
  - Scope 验证
  - 优先级选择
  - 路由逻辑
  - 缓存机制
- [x] 集成测试 (`test_multi_agent_integration.py` - 7 个测试)
  - 多智能体路由工作流
  - 实例生命周期
  - 并发访问
  - 禁用代理路由
  - 懒加载验证

### Phase 5: 待实现功能

- [ ] CoPawAgent 与 AgentInstanceManager 的完整集成（需要 app/runner 整合）
- [ ] E2E 测试
- [ ] 性能优化（大规模实例场景）
- [ ] 文档更新（用户文档）

## 8. 向后兼容

- 保持现有 `Persona` 模型和 API
- 新增 `AgentInstance` 模型和 API
- 可选择使用哪种模式
- 默认：单智能体 + Persona 提示
- 配置启用：多智能体路由

## 9. 实现计划

### Phase 1: 完善主智能体路由功能 (优先级：高)

**目标**：实现主智能体作为 PM/管家角色，能够路由消息到专家智能体

**任务**：
1. 修改 `CoPawAgent.reply()` 方法，添加路由逻辑
2. 实现 `AgentInstanceManager.get_or_create_agent()` 懒加载
3. 添加专家智能体缓存机制
4. 编写单元测试

**文件修改**：
- `src/copaw/agents/react_agent.py` - 添加路由逻辑
- `src/copaw/agents/agent_instance/manager.py` - 添加缓存和懒加载
- `tests/agents/test_multi_agent_routing.py` - 新增测试

### Phase 2: 整合 Persona 到智能体实例 (优先级：中)

**目标**：将 Persona 功能整合到智能体实例管理，简化前端菜单

**任务**：
1. 前端菜单调整：Personas -> 智能体实例（移动到 Agent 分组）
2. 后端 API 保持不变，AgentInstance 已包含 Persona 功能
3. 保留 Persona API 用于向后兼容

**文件修改**：
- `console/src/layouts/Sidebar.tsx` - 添加 agent-instances 到 Agent 分组
- `console/src/pages/Settings/Personas/` - 可考虑移除或标记为废弃
- `console/src/pages/Agent/Instances.tsx` - 已有，确保功能完整

### Phase 3: 完善测试和文档 (优先级：中)

**任务**：
1. 编写集成测试
2. 更新文档
3. 性能优化

## 10. 前端菜单结构

### 当前结构
```
智能体 (Agent) 分组:
  - 工作区 (workspace)
  - 技能 (skills)
  - MCP
  - 运行配置 (agent-config)

设置 (Settings) 分组:
  - 模型 (models)
  - 环境变量 (environments)
  - 规则 (rules)
  - 角色 (personas)  <-- 需要移动到 Agent 分组
```

### 目标结构
```
智能体 (Agent) 分组:
  - 工作区 (workspace)
  - 技能 (skills)
  - MCP
  - 智能体实例 (agent-instances)  <-- 新增，包含原 personas 功能
  - 运行配置 (agent-config)

设置 (Settings) 分组:
  - 模型 (models)
  - 环境变量 (environments)
  - 规则 (rules)
```
