# -*- coding: utf-8 -*-
"""Tests for multi-agent routing and AgentInstanceManager."""
import pytest
import asyncio
import tempfile
import shutil
from pathlib import Path
from datetime import datetime

from copaw.agents.agent_instance import (
    AgentInstanceManager,
    AgentInstance,
    AgentScope,
    ModelConfig,
    AgentRouter,
    RoutingResult,
)


@pytest.fixture
def temp_instances_dir():
    """Create a temporary directory for agent instance tests."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def instance_manager(temp_instances_dir):
    """Create an AgentInstanceManager with temporary storage."""
    manager = AgentInstanceManager(save_dir=temp_instances_dir)
    return manager


@pytest.mark.asyncio
async def test_create_instance_global(instance_manager):
    """Test creating a global agent instance with optimized prompt."""
    instance = await instance_manager.create_instance(
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

    assert instance.name == "Friday 智能助手"
    assert instance.scope == AgentScope.GLOBAL
    assert instance.enabled is True
    assert instance.id is not None

    # Verify it was saved
    loaded_instance = await instance_manager.get_instance(instance.id)
    assert loaded_instance is not None
    assert loaded_instance.name == "Friday 智能助手"


@pytest.mark.asyncio
async def test_create_instance_user(instance_manager):
    """Test creating a user-scoped agent instance with optimized prompt."""
    instance = await instance_manager.create_instance(
        name="VIP 私人助理",
        description="为 VIP 用户提供个性化服务的私人助理",
        agent_type="personal_assistant",
        system_prompt="""你是一位专业的私人助理，名叫「贴心管家」。你的职责是帮助用户高效管理个人事务、安排日程、提供生活建议。

【核心职责】
- 日程管理：安排会议、提醒重要事项、协调时间冲突
- 信息管理：整理邮件、筛选信息、汇总要点
- 出行规划：预订行程、制定路线、准备清单
- 生活建议：餐厅推荐、活动安排、购物建议

【工作风格】
- 细致周到，考虑周全
- 主动预见，提前准备
- 高效执行，及时反馈
- 严守隐私，值得信赖

【沟通特点】
- 称呼得体，根据用户偏好调整
- 语气亲切自然，像朋友般交流
- 理解用户习惯和偏好，提供个性化建议
- 在用户忙碌时，沟通简洁高效""",
        scope=AgentScope.USER,
        user_ids="user1 user2 user3",
        enabled=True,
    )

    assert instance.name == "VIP 私人助理"
    assert instance.scope == AgentScope.USER
    assert instance.user_ids == "user1 user2 user3"

    # Verify user_id_list property
    assert instance.user_id_list == ["user1", "user2", "user3"]


@pytest.mark.asyncio
async def test_create_instance_channel(instance_manager):
    """Test creating a channel-scoped agent instance with optimized prompt."""
    instance = await instance_manager.create_instance(
        name="客服代表",
        description="钉钉平台的专业客户服务代表",
        agent_type="customer_service",
        system_prompt="""你是一位专业的客户服务代表，名叫「贴心助手」。你的职责是帮助客户解决问题、处理投诉、提供优质的售后服务。

【服务态度】
- 客户至上，真诚关心客户需求
- 耐心倾听，不打断客户陈述
- 共情理解，对客户的不满表示理解
- 积极主动，不推诿责任

【处理流程】
1. 倾听记录：完整记录客户问题和诉求
2. 确认理解：复述客户问题，确保没有误解
3. 表达歉意：对客户的不佳体验表示歉意
4. 解决方案：提供明确的解决步骤和时间预期
5. 跟进确认：确认问题是否得到解决

【沟通技巧】
- 使用礼貌用语：「您好」「请问」「感谢您的耐心」
- 避免负面词汇：「不行」「不能」「没办法」
- 用正面表达：「我可以帮您...」「建议您...」
- 对情绪激动的客户，先安抚情绪再解决问题""",
        scope=AgentScope.CHANNEL,
        channel="dingtalk",
        enabled=True,
    )

    assert instance.name == "客服代表"
    assert instance.scope == AgentScope.CHANNEL
    assert instance.channel == "dingtalk"


@pytest.mark.asyncio
async def test_create_instance_user_channel(instance_manager):
    """Test creating a user+channel scoped agent instance with optimized prompt."""
    instance = await instance_manager.create_instance(
        name="优秀教师",
        description="为钉钉特定用户提供的在线教师",
        agent_type="teacher",
        system_prompt="""你是一位拥有 20 年教学经验的资深教师，名叫「智学导师」。你的使命是帮助学生有效学习、理解知识、培养思维能力。

【教育理念】
- 以学生为中心，因材施教
- 注重理解而非死记硬背
- 培养批判性思维和独立思考能力
- 鼓励学生提问，营造安全的试错环境

【教学方法】
1. 启发式教学：通过提问引导学生思考，而非直接给出答案
2. 循序渐进：从已知到未知，从简单到复杂
3. 举例说明：用生活中的实例解释抽象概念
4. 检查理解：定期确认学生是否真正理解

【沟通风格】
- 耐心细致，语气温和但坚定
- 善用比喻和类比，让复杂概念通俗易懂
- 对学生的进步给予具体、真诚的肯定
- 当学生遇到困难时，表达理解并提供鼓励

【回复结构】
1. 先确认理解学生的问题
2. 分析问题的关键点和难点
3. 分步骤讲解，每一步都确认理解
4. 提供练习建议或延伸思考
5. 鼓励性结语""",
        scope=AgentScope.USER_CHANNEL,
        channel="dingtalk",
        user_ids="student1 student2",
        enabled=True,
    )

    assert instance.name == "优秀教师"
    assert instance.scope == AgentScope.USER_CHANNEL
    assert instance.channel == "dingtalk"
    assert instance.user_ids == "student1 student2"


@pytest.mark.asyncio
async def test_create_instance_validation_error(instance_manager):
    """Test validation errors for scope-specific fields."""
    # CHANNEL scope without channel should raise error
    with pytest.raises(ValueError, match="channel is required"):
        await instance_manager.create_instance(
            name="Invalid",
            description="Invalid instance",
            agent_type="test",
            system_prompt="Test",
            scope=AgentScope.CHANNEL,
        )

    # USER scope without user_ids should raise error
    with pytest.raises(ValueError, match="user_ids is required"):
        await instance_manager.create_instance(
            name="Invalid",
            description="Invalid instance",
            agent_type="test",
            system_prompt="Test",
            scope=AgentScope.USER,
        )


@pytest.mark.asyncio
async def test_get_active_instance_priority(instance_manager):
    """Test that get_active_instance returns highest priority match."""
    # Create global instance
    global_inst = await instance_manager.create_instance(
        name="Global",
        description="Global assistant",
        agent_type="assistant",
        system_prompt="Global",
        scope=AgentScope.GLOBAL,
    )

    # Create channel instance
    channel_inst = await instance_manager.create_instance(
        name="Channel",
        description="Channel assistant",
        agent_type="assistant",
        system_prompt="Channel",
        scope=AgentScope.CHANNEL,
        channel="dingtalk",
    )

    # Create user instance
    user_inst = await instance_manager.create_instance(
        name="User",
        description="User assistant",
        agent_type="assistant",
        system_prompt="User",
        scope=AgentScope.USER,
        user_ids="user1",
    )

    # Create user+channel instance
    user_channel_inst = await instance_manager.create_instance(
        name="User+Channel",
        description="User+Channel assistant",
        agent_type="assistant",
        system_prompt="User+Channel",
        scope=AgentScope.USER_CHANNEL,
        channel="dingtalk",
        user_ids="user1",
    )

    # Test priority: USER_CHANNEL > USER > CHANNEL > GLOBAL
    # For user1 on dingtalk, should get USER_CHANNEL
    active = await instance_manager.get_active_instance(
        channel="dingtalk",
        user_id="user1",
    )
    assert active is not None
    assert active.id == user_channel_inst.id
    assert active.scope == AgentScope.USER_CHANNEL

    # For user2 on dingtalk (not in user_ids), should get CHANNEL
    active = await instance_manager.get_active_instance(
        channel="dingtalk",
        user_id="user2",
    )
    assert active is not None
    assert active.id == channel_inst.id

    # For user1 on feishu (not in channel scope), should get USER
    active = await instance_manager.get_active_instance(
        channel="feishu",
        user_id="user1",
    )
    assert active is not None
    assert active.id == user_inst.id

    # For unknown user on unknown channel, should get GLOBAL
    active = await instance_manager.get_active_instance(
        channel="wechat",
        user_id="stranger",
    )
    assert active is not None
    assert active.id == global_inst.id


@pytest.mark.asyncio
async def test_is_applicable_to(instance_manager):
    """Test AgentInstance.is_applicable_to method."""
    # Create user+channel instance
    inst = await instance_manager.create_instance(
        name="Test",
        description="Test",
        agent_type="test",
        system_prompt="Test",
        scope=AgentScope.USER_CHANNEL,
        channel="dingtalk",
        user_ids="user1 user2",
    )

    # Should match
    assert inst.is_applicable_to(channel="dingtalk", user_id="user1") is True
    assert inst.is_applicable_to(channel="dingtalk", user_id="user2") is True

    # Should not match - wrong channel
    assert inst.is_applicable_to(channel="feishu", user_id="user1") is False

    # Should not match - wrong user
    assert inst.is_applicable_to(channel="dingtalk", user_id="user3") is False

    # Test disabled instance
    await instance_manager.disable_instance(inst.id)
    inst = await instance_manager.get_instance(inst.id)
    assert inst.is_applicable_to(channel="dingtalk", user_id="user1") is False


@pytest.mark.asyncio
async def test_get_priority_score(instance_manager):
    """Test AgentInstance.get_priority_score method."""
    # Create instances with different scopes
    global_inst = await instance_manager.create_instance(
        name="Global",
        description="Global",
        agent_type="test",
        system_prompt="Global",
        scope=AgentScope.GLOBAL,
    )

    channel_inst = await instance_manager.create_instance(
        name="Channel",
        description="Channel",
        agent_type="test",
        system_prompt="Channel",
        scope=AgentScope.CHANNEL,
        channel="dingtalk",
    )

    user_inst = await instance_manager.create_instance(
        name="User",
        description="User",
        agent_type="test",
        system_prompt="User",
        scope=AgentScope.USER,
        user_ids="user1",
    )

    user_channel_inst = await instance_manager.create_instance(
        name="User+Channel",
        description="User+Channel",
        agent_type="test",
        system_prompt="User+Channel",
        scope=AgentScope.USER_CHANNEL,
        channel="dingtalk",
        user_ids="user1",
    )

    # Test priority scores
    assert global_inst.get_priority_score(channel="dingtalk", user_id="user1") == 1
    assert channel_inst.get_priority_score(channel="dingtalk", user_id="user1") == 2
    assert user_inst.get_priority_score(channel="dingtalk", user_id="user1") == 3
    assert user_channel_inst.get_priority_score(channel="dingtalk", user_id="user1") == 4

    # Test non-applicable returns 0
    assert channel_inst.get_priority_score(channel="feishu", user_id="user1") == 0


@pytest.mark.asyncio
async def test_list_instances(instance_manager):
    """Test listing agent instances with filters."""
    # Create multiple instances
    await instance_manager.create_instance(
        name="Global 1",
        description="Global",
        agent_type="assistant",
        system_prompt="Global",
        scope=AgentScope.GLOBAL,
        enabled=True,
    )

    await instance_manager.create_instance(
        name="Disabled",
        description="Disabled",
        agent_type="assistant",
        system_prompt="Disabled",
        scope=AgentScope.GLOBAL,
        enabled=False,
    )

    await instance_manager.create_instance(
        name="User",
        description="User",
        agent_type="assistant",
        system_prompt="User",
        scope=AgentScope.USER,
        user_ids="user1",
        enabled=True,
    )

    # List all (enabled only by default)
    instances = await instance_manager.list_instances()
    assert len(instances) == 2  # Only enabled

    # List all including disabled
    instances = await instance_manager.list_instances(enabled_only=False)
    assert len(instances) == 3

    # Filter by scope
    instances = await instance_manager.list_instances(scope=AgentScope.GLOBAL)
    assert len(instances) == 1  # Only Global 1 (enabled)


@pytest.mark.asyncio
async def test_update_instance(instance_manager):
    """Test updating an agent instance."""
    instance = await instance_manager.create_instance(
        name="Original",
        description="Original description",
        agent_type="assistant",
        system_prompt="Original prompt",
        scope=AgentScope.GLOBAL,
    )

    # Update fields
    updated = await instance_manager.update_instance(
        instance_id=instance.id,
        name="Updated",
        description="Updated description",
        system_prompt="Updated prompt",
    )

    assert updated is not None
    assert updated.name == "Updated"
    assert updated.description == "Updated description"
    assert updated.system_prompt == "Updated prompt"

    # Verify persistence
    loaded = await instance_manager.get_instance(instance.id)
    assert loaded.name == "Updated"


@pytest.mark.asyncio
async def test_delete_instance(instance_manager):
    """Test deleting an agent instance."""
    instance = await instance_manager.create_instance(
        name="To Delete",
        description="Will be deleted",
        agent_type="assistant",
        system_prompt="Delete me",
        scope=AgentScope.GLOBAL,
    )

    # Delete
    success = await instance_manager.delete_instance(instance.id)
    assert success is True

    # Verify deleted
    loaded = await instance_manager.get_instance(instance.id)
    assert loaded is None

    # Delete non-existent should return False
    success = await instance_manager.delete_instance("non-existent-id")
    assert success is False


@pytest.mark.asyncio
async def test_toggle_instance(instance_manager):
    """Test enabling and disabling agent instances."""
    instance = await instance_manager.create_instance(
        name="Toggle Test",
        description="Toggle test",
        agent_type="assistant",
        system_prompt="Toggle",
        scope=AgentScope.GLOBAL,
        enabled=True,
    )

    # Disable
    success = await instance_manager.disable_instance(instance.id)
    assert success is True

    loaded = await instance_manager.get_instance(instance.id)
    assert loaded.enabled is False

    # Enable
    success = await instance_manager.enable_instance(instance.id)
    assert success is True

    loaded = await instance_manager.get_instance(instance.id)
    assert loaded.enabled is True


@pytest.mark.asyncio
async def test_persistence(instance_manager, temp_instances_dir):
    """Test that agent instances persist across manager reloads."""
    # Create instance
    await instance_manager.create_instance(
        name="Persistent",
        description="Should persist",
        agent_type="assistant",
        system_prompt="Persistent",
        scope=AgentScope.GLOBAL,
    )

    # Create new manager with same storage
    new_manager = AgentInstanceManager(save_dir=temp_instances_dir)
    await new_manager.load()

    # Verify instance was loaded
    instances = await new_manager.list_instances()
    assert len(instances) == 1
    assert instances[0].name == "Persistent"


@pytest.mark.asyncio
async def test_agent_router(instance_manager):
    """Test AgentRouter routing logic."""
    # Create instances
    await instance_manager.create_instance(
        name="Global",
        description="Global assistant",
        agent_type="assistant",
        system_prompt="Global",
        scope=AgentScope.GLOBAL,
    )

    await instance_manager.create_instance(
        name="DingTalk Agent",
        description="DingTalk specific agent",
        agent_type="assistant",
        system_prompt="DingTalk",
        scope=AgentScope.CHANNEL,
        channel="dingtalk",
    )

    router = AgentRouter(instance_manager)

    # Test routing for dingtalk user
    result = await router.route_request(
        channel="dingtalk",
        user_id="user1",
        message="Hello",
    )

    assert isinstance(result, RoutingResult)
    assert result.matched_instance is not None
    assert result.matched_instance.name == "DingTalk Agent"
    assert "priority" in result.reason.lower()

    # Test routing for unknown channel (should get global)
    result = await router.route_request(
        channel="unknown",
        user_id="user1",
        message="Hello",
    )

    assert result.matched_instance is not None
    assert result.matched_instance.name == "Global"


@pytest.mark.asyncio
async def test_get_routing_candidates(instance_manager):
    """Test getting all routing candidates for a context."""
    # Create multiple applicable instances
    global_inst = await instance_manager.create_instance(
        name="Global",
        description="Global",
        agent_type="assistant",
        system_prompt="Global",
        scope=AgentScope.GLOBAL,
    )

    channel_inst = await instance_manager.create_instance(
        name="Channel",
        description="Channel",
        agent_type="assistant",
        system_prompt="Channel",
        scope=AgentScope.CHANNEL,
        channel="dingtalk",
    )

    router = AgentRouter(instance_manager)

    candidates = await router.get_routing_candidates(
        channel="dingtalk",
        user_id="user1",
    )

    # Should return all applicable instances sorted by priority
    assert len(candidates) == 2
    # First should be highest priority (CHANNEL)
    assert candidates[0].id == channel_inst.id
    # Second should be lower priority (GLOBAL)
    assert candidates[1].id == global_inst.id


# Phase 1: CoPawAgent integration tests (require CoPawAgent to be importable)

@pytest.mark.asyncio
async def test_get_or_create_agent_lazy_loading(instance_manager):
    """Test that get_or_create_agent uses lazy loading."""
    instance = await instance_manager.create_instance(
        name="Lazy Test",
        description="Test lazy loading",
        agent_type="assistant",
        system_prompt="You are a lazy loading test agent.",
        scope=AgentScope.GLOBAL,
    )

    # First call should create agent
    agent1 = await instance_manager.get_or_create_agent(
        instance_id=instance.id,
        channel="console",
        user_id="test_user",
    )

    # Second call should return cached agent
    agent2 = await instance_manager.get_or_create_agent(
        instance_id=instance.id,
        channel="console",
        user_id="test_user",
    )

    # Should be the same instance (cached)
    assert agent1 is agent2


@pytest.mark.asyncio
async def test_invalidate_agent_cache(instance_manager):
    """Test invalidating agent cache."""
    instance = await instance_manager.create_instance(
        name="Cache Test",
        description="Test cache invalidation",
        agent_type="assistant",
        system_prompt="You are a cache test agent.",
        scope=AgentScope.GLOBAL,
    )

    # Create cached agent
    await instance_manager.get_or_create_agent(
        instance_id=instance.id,
        channel="console",
        user_id="test_user",
    )

    # Invalidate specific cache
    await instance_manager.invalidate_agent_cache(instance_id=instance.id)
    # Should not raise, cache should be cleared for this instance

    # Invalidate all cache
    await instance_manager.get_or_create_agent(
        instance_id=instance.id,
        channel="console",
        user_id="test_user",
    )
    await instance_manager.invalidate_agent_cache()
    # All cache should be cleared


@pytest.mark.asyncio
async def test_process_with_agent_not_found(instance_manager):
    """Test process_with_agent with non-existent instance."""
    with pytest.raises(ValueError, match="not found"):
        await instance_manager.process_with_agent(
            instance_id="non-existent-id",
            msg=None,
            channel="console",
            user_id="test_user",
        )
