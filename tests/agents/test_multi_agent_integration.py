# -*- coding: utf-8 -*-
"""Integration tests for multi-agent system.

These tests verify the end-to-end functionality of the multi-agent routing system.
"""
import pytest
import asyncio
import tempfile
import shutil
from pathlib import Path

from copaw.agents.agent_instance import (
    AgentInstanceManager,
    AgentInstance,
    AgentScope,
    AgentRouter,
)


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.mark.asyncio
async def test_multi_agent_routing_workflow(temp_dir):
    """Test complete multi-agent routing workflow.

    This test simulates:
    1. Creating multiple agent instances with different scopes
    2. Routing messages from different channel/user contexts
    3. Verifying correct agent is selected
    """
    # Setup: Create agent instances
    manager = AgentInstanceManager(save_dir=temp_dir)
    await manager.load()

    # Create a global default agent
    global_agent = await manager.create_instance(
        name="Friday 智能助手",
        description="经验丰富的全能型智能助理",
        agent_type="assistant",
        system_prompt="""你是一位经验丰富的智能助理，名叫 Friday。你的职责是协助用户处理各种日常任务和查询。

【核心能力】
- 信息查询与整理：快速定位关键信息，提供结构化总结
- 任务规划：帮助用户分解复杂任务，制定可执行的步骤
- 文档处理：撰写、编辑、润色各类文档
- 问题分析：运用逻辑思维，提供清晰的因果分析

【沟通风格】
- 友好亲切，但不失专业
- 简洁明了，避免冗长啰嗦
- 主动询问澄清问题，确保理解用户需求
- 遇到不确定的情况时，诚实告知并提供替代方案

【行为准则】
1. 始终以帮助用户解决问题为首要目标
2. 对于复杂任务，主动提供分步骤的建议
3. 尊重用户的决策，提供建议但不强加意见
4. 保护用户隐私，不主动询问或存储敏感信息""",
        scope=AgentScope.GLOBAL,
        enabled=True,
    )

    # Create a DingTalk-specific customer service agent
    dingtalk_agent = await manager.create_instance(
        name="客服代表",
        description="钉钉平台的专业客户服务代表",
        agent_type="customer_service",
        system_prompt="""你是一位专业的客户服务代表，名叫「贴心助手」。你的职责是帮助客户解决问题、处理投诉、提供优质的售后服务。

【服务态度】
- 客户至上，真诚关心客户需求
- 耐心倾听，不打断客户陈述
- 共情理解，对客户的不满表示理解
- 积极主动，不推诿责任

【沟通技巧】
- 使用礼貌用语：「您好」「请问」「感谢您的耐心」
- 避免负面词汇：「不行」「不能」「没办法」
- 用正面表达：「我可以帮您...」「建议您...」""",
        scope=AgentScope.CHANNEL,
        channel="dingtalk",
        enabled=True,
    )

    # Create a VIP user-specific agent
    vip_agent = await manager.create_instance(
        name="VIP 私人助理",
        description="为 VIP 用户提供个性化服务的私人助理",
        agent_type="personal_assistant",
        system_prompt="""你是一位专业的私人助理，名叫「贴心管家」。你的职责是帮助用户高效管理个人事务、安排日程、提供生活建议。

【工作风格】
- 细致周到，考虑周全
- 主动预见，提前准备
- 高效执行，及时反馈
- 严守隐私，值得信赖

【沟通特点】
- 称呼得体，根据用户偏好调整
- 语气亲切自然，像朋友般交流
- 理解用户习惯和偏好，提供个性化建议""",
        scope=AgentScope.USER,
        user_ids="vip_user_001 vip_user_002",
        enabled=True,
    )

    # Create a teacher agent for specific users on specific channel
    teacher_agent = await manager.create_instance(
        name="优秀教师",
        description="为钉钉特定用户提供的在线教师",
        agent_type="teacher",
        system_prompt="""你是一位拥有 20 年教学经验的资深教师，名叫「智学导师」。你的使命是帮助学生有效学习、理解知识、培养思维能力。

【教育理念】
- 以学生为中心，因材施教
- 注重理解而非死记硬背
- 培养批判性思维和独立思考能力

【教学方法】
1. 启发式教学：通过提问引导学生思考
2. 循序渐进：从已知到未知，从简单到复杂
3. 举例说明：用生活中的实例解释抽象概念
4. 检查理解：定期确认学生是否真正理解

【沟通风格】
- 耐心细致，语气温和但坚定
- 善用比喻和类比，让复杂概念通俗易懂
- 对学生的进步给予具体、真诚的肯定""",
        scope=AgentScope.USER_CHANNEL,
        channel="dingtalk",
        user_ids="student_001 student_002",
        enabled=True,
    )

    # Create router
    router = AgentRouter(manager)

    # Test Case 1: Regular user on unknown channel -> Global agent
    result = await router.route_request(
        channel="wechat",
        user_id="regular_user",
        message="Hello",
    )
    assert result.matched_instance is not None
    assert result.matched_instance.id == global_agent.id
    assert result.priority_score == 1

    # Test Case 2: Regular user on DingTalk -> DingTalk agent
    result = await router.route_request(
        channel="dingtalk",
        user_id="regular_user",
        message="I need help with my order",
    )
    assert result.matched_instance is not None
    assert result.matched_instance.id == dingtalk_agent.id
    assert result.priority_score == 2

    # Test Case 3: VIP user on unknown channel -> VIP agent
    result = await router.route_request(
        channel="feishu",
        user_id="vip_user_001",
        message="I need assistance",
    )
    assert result.matched_instance is not None
    assert result.matched_instance.id == vip_agent.id
    assert result.priority_score == 3

    # Test Case 4: Student on DingTalk -> Teacher agent (highest priority)
    result = await router.route_request(
        channel="dingtalk",
        user_id="student_001",
        message="I have a question about the lesson",
    )
    assert result.matched_instance is not None
    assert result.matched_instance.id == teacher_agent.id
    assert result.priority_score == 4

    # Test Case 5: VIP user on DingTalk -> Teacher agent if student, otherwise VIP agent
    # If VIP user is also a student
    result = await router.route_request(
        channel="dingtalk",
        user_id="student_001",  # Also in vip_user_001 list? No, so different user
        message="Hello",
    )
    # student_001 is in teacher_agent's user_ids, so teacher agent wins
    assert result.matched_instance is not None
    assert result.matched_instance.id == teacher_agent.id


@pytest.mark.asyncio
async def test_agent_instance_lifecycle(temp_dir):
    """Test complete lifecycle of agent instances.

    This test verifies:
    1. Creating instances
    2. Updating instances
    3. Enabling/disabling instances
    4. Deleting instances
    5. Persistence across manager reloads
    """
    # Phase 1: Create and modify
    manager1 = AgentInstanceManager(save_dir=temp_dir)
    await manager1.load()

    # Create instance
    agent = await manager1.create_instance(
        name="Test Agent",
        description="Initial description",
        agent_type="test",
        system_prompt="Initial prompt",
        scope=AgentScope.GLOBAL,
        enabled=True,
    )
    original_id = agent.id
    assert agent.name == "Test Agent"
    assert agent.enabled is True

    # Update instance
    updated = await manager1.update_instance(
        instance_id=original_id,
        name="Updated Agent",
        description="Updated description",
    )
    assert updated.name == "Updated Agent"
    assert updated.description == "Updated description"

    # Disable instance
    await manager1.disable_instance(original_id)
    disabled = await manager1.get_instance(original_id)
    assert disabled.enabled is False

    # Verify disabled agent is not returned in enabled_only listing
    enabled_agents = await manager1.list_instances(enabled_only=True)
    assert len(enabled_agents) == 0

    # Verify disabled agent is returned in all listing
    all_agents = await manager1.list_instances(enabled_only=False)
    assert len(all_agents) == 1

    # Phase 2: Reload from disk
    manager2 = AgentInstanceManager(save_dir=temp_dir)
    await manager2.load()

    # Verify persistence
    reloaded = await manager2.get_instance(original_id)
    assert reloaded is not None
    assert reloaded.name == "Updated Agent"
    assert reloaded.description == "Updated description"
    assert reloaded.enabled is False

    # Re-enable
    await manager2.enable_instance(original_id)
    reloaded = await manager2.get_instance(original_id)
    assert reloaded.enabled is True

    # Phase 3: Delete
    await manager2.delete_instance(original_id)
    deleted = await manager2.get_instance(original_id)
    assert deleted is None


@pytest.mark.asyncio
async def test_concurrent_agent_access(temp_dir):
    """Test concurrent access to agent instances."""
    manager = AgentInstanceManager(save_dir=temp_dir)
    await manager.load()

    # Create initial instance
    agent = await manager.create_instance(
        name="Concurrent Test",
        description="Testing concurrent access",
        agent_type="test",
        system_prompt="Test prompt",
        scope=AgentScope.GLOBAL,
        enabled=True,
    )

    # Simulate concurrent read operations
    async def read_agent():
        result = await manager.get_instance(agent.id)
        return result

    # Run multiple concurrent reads
    tasks = [read_agent() for _ in range(10)]
    results = await asyncio.gather(*tasks)

    # All should return the same agent
    for result in results:
        assert result is not None
        assert result.id == agent.id


@pytest.mark.asyncio
async def test_router_with_no_matching_agents(temp_dir):
    """Test router behavior when no agents match the context."""
    manager = AgentInstanceManager(save_dir=temp_dir)
    await manager.load()

    # Create only a channel-specific agent
    await manager.create_instance(
        name="DingTalk Only",
        description="Only for DingTalk",
        agent_type="test",
        system_prompt="Test",
        scope=AgentScope.CHANNEL,
        channel="dingtalk",
        enabled=True,
    )

    router = AgentRouter(manager)

    # Request for different channel should return no match
    result = await router.route_request(
        channel="feishu",
        user_id="any_user",
        message="Hello",
    )

    # With current implementation, GLOBAL is default fallback
    # If no GLOBAL exists, should return None or appropriate response
    assert result.matched_instance is None


@pytest.mark.asyncio
async def test_disabled_agents_not_routed(temp_dir):
    """Test that disabled agents are not selected for routing."""
    manager = AgentInstanceManager(save_dir=temp_dir)
    await manager.load()

    # Create global agent and disable it
    global_agent = await manager.create_instance(
        name="Disabled Global",
        description="Should not be routed",
        agent_type="test",
        system_prompt="Test",
        scope=AgentScope.GLOBAL,
        enabled=True,
    )
    await manager.disable_instance(global_agent.id)

    # Create enabled global agent
    active_agent = await manager.create_instance(
        name="Active Global",
        description="Should be routed",
        agent_type="test",
        system_prompt="Test",
        scope=AgentScope.GLOBAL,
        enabled=True,
    )

    router = AgentRouter(manager)

    # Should route to active agent, not disabled one
    result = await router.route_request(
        channel="any",
        user_id="any",
        message="Hello",
    )

    assert result.matched_instance is not None
    assert result.matched_instance.id == active_agent.id
    assert result.matched_instance.id != global_agent.id


@pytest.mark.asyncio
async def test_get_or_create_agent_workflow(temp_dir):
    """Test the get_or_create_agent workflow for lazy loading."""
    manager = AgentInstanceManager(save_dir=temp_dir)
    await manager.load()

    # Create instance
    agent_instance = await manager.create_instance(
        name="Lazy Load Test",
        description="Testing lazy loading",
        agent_type="test",
        system_prompt="You are a test agent for lazy loading verification.",
        scope=AgentScope.GLOBAL,
        enabled=True,
    )

    # First call - should create
    agent1 = await manager.get_or_create_agent(
        instance_id=agent_instance.id,
        channel="console",
        user_id="test_user",
    )
    assert agent1 is not None

    # Second call - should return cached
    agent2 = await manager.get_or_create_agent(
        instance_id=agent_instance.id,
        channel="console",
        user_id="test_user",
    )
    assert agent2 is not None
    assert agent1 is agent2  # Same object reference

    # Invalidate cache
    await manager.invalidate_agent_cache(instance_id=agent_instance.id)

    # Third call - should create new instance
    agent3 = await manager.get_or_create_agent(
        instance_id=agent_instance.id,
        channel="console",
        user_id="test_user",
    )
    assert agent3 is not None
    # Note: agent3 may or may not be the same as agent1 depending on implementation


@pytest.mark.asyncio
async def test_priority_score_consistency(temp_dir):
    """Test that priority scores are consistent across multiple calls."""
    manager = AgentInstanceManager(save_dir=temp_dir)
    await manager.load()

    # Create instances with all scope types
    instances = {}
    scopes = [
        (AgentScope.GLOBAL, "global", {}),
        (AgentScope.CHANNEL, "channel", {"channel": "dingtalk"}),
        (AgentScope.USER, "user", {"user_ids": "user1"}),
        (AgentScope.USER_CHANNEL, "user_channel", {"channel": "dingtalk", "user_ids": "user1"}),
    ]

    for scope, name, kwargs in scopes:
        inst = await manager.create_instance(
            name=name.capitalize(),
            description=f"{name} scope test",
            agent_type="test",
            system_prompt="Test",
            scope=scope,
            **kwargs,
        )
        instances[name] = inst

    # Test multiple times to ensure consistency
    for _ in range(5):
        # For user1 on dingtalk, all agents should be applicable
        active = await manager.get_active_instance(
            channel="dingtalk",
            user_id="user1",
        )

        # USER_CHANNEL should always win (priority 4)
        assert active is not None
        assert active.id == instances["user_channel"].id
