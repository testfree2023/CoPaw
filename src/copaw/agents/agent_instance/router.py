# -*- coding: utf-8 -*-
"""Agent Router for CoPaw multi-agent system.

This module provides routing capabilities to dispatch messages
to the most appropriate agent instance based on context.

Features:
- Context-based agent routing (channel, user)
- Priority-based selection
- Fallback to default agent
- Logging and debug information

Example:
    >>> from copaw.agents.agent_instance import AgentRouter, AgentInstanceManager
    >>>
    >>> router = AgentRouter(instance_manager)
    >>>
    >>> # Route a message from DingTalk user
    >>> result = await router.route_request(
    ...     channel="dingtalk",
    ...     user_id="user123",
    ...     message="你好，我是老师",
    ... )
    >>>
    >>> if result.matched_instance:
    ...     print(f"Routing to: {result.matched_instance.name}")
    >>> else:
    ...     print("Using default agent")
"""
import logging
from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING, Dict, List

if TYPE_CHECKING:
    from .manager import AgentInstanceManager
    from .models import AgentInstance
else:
    # Runtime import for type hints in function bodies
    from .models import AgentInstance

logger = logging.getLogger(__name__)

# Intent keywords for agent type matching
# Each agent_type has a list of keywords that trigger intent-based routing
INTENT_KEYWORDS = {
    "expert": [
        # Programming & Development
        "代码", "编程", "写程序", "开发", "debug", "debugging", "bug", "error",
        "函数", "class", "def ", "import ", "代码审查", "重构", "架构",
        "api", "sdk", "框架", "library", "package", "模块", "接口",
        "git", "pull request", "commit", "merge", "分支", "部署", "ci/cd",
        "数据库", "sql", "nosql", "redis", "mongodb", "mysql", "postgresql",
        "前端", "后端", "fullstack", "react", "vue", "angular", "nodejs",
        "python", "java", "javascript", "typescript", "go", "rust", "c++",
        "docker", "kubernetes", "k8s", "容器", "微服务", "cloud", "aws", "azure",
        "性能优化", "并发", "异步", "async", "多线程", "内存泄漏", "cpu",
        # Algorithms & Data Structures
        "算法", "排序", "冒泡", "快速排序", "归并", "查找", "树", "图", "链表",
        "栈", "队列", "堆", "哈希", "递归", "动态规划", "贪心", "回溯",
        # Tech-related questions
        "怎么写代码", "怎么实现", "技术方案", "系统设计", "技术选型",
    ],
    "teacher": [
        # Learning & Education
        "学习", "教学", "辅导", "作业", "考试", "题目", "解答", "讲解",
        "怎么学", "不懂", "理解", "知识点", "概念", "原理", "公式",
        "学校", "老师", "学生", "课程", "课程表", "作业", "练习",
        "数学", "物理", "化学", "生物", "历史", "地理", "英语", "语文",
        "解题", "步骤", "思路", "方法", "技巧", "记忆", "背诵",
        # Education-related questions
        "怎么教", "如何学习", "学习计划", "复习", "预习", "升学",
    ],
    "investor": [
        # Investment & Finance
        "股票", "基金", "债券", "期货", "期权", "外汇", "加密货币", "bitcoin",
        "投资", "理财", "资产", "配置", "组合", "收益", "回报", "分红",
        "风险", "估值", "pe", "pb", "roe", "财报", "年报", "季报",
        "买入", "卖出", "持仓", "仓位", "止盈", "止损", "建仓", "加仓",
        "银行", "保险", "信托", "贷款", "利率", "通胀", "gdp", "cpi",
        "经济", "宏观", "政策", "央行", "美联储", "加息", "降息",
        # Stock market specific
        "港股", "a 股", "美股", "科创板", "创业板", "主板", "新股",
        "走势", "行情", "股价", "市值", "涨停", "跌停", "复盘",
        "分析", "预测", "目标价", "评级", "投行", "券商",
        # Company names (common)
        "阿里巴巴", "腾讯", "美团", "京东", "拼多多", "字节",
        "特斯拉", "苹果", "微软", "谷歌", "亚马逊", "英伟达",
        "茅台", "平安", "招商", "工行", "建行",
        # Finance-related questions
        "怎么投资", "理财建议", "资产配置", "财务规划", "退休规划",
    ],
    "assistant": [
        # Customer Service & Personal Assistant
        "客服", "售后", "投诉", "反馈", "建议", "问题", "帮助",
        "订单", "物流", "快递", "发货", "收货", "退换货", "退款",
        "预约", "预订", "取消", "修改", "查询", "状态",
        "日程", "提醒", "会议", "安排", "时间", "计划", "待办",
        "推荐", "攻略", "指南", "怎么操作", "如何使用",
    ],
}

# Default agent type when no specific intent is detected
DEFAULT_AGENT_TYPE = "custom"


@dataclass
class RoutingResult:
    """Result of agent routing decision.

    Attributes:
        matched_instance: The matched agent instance, or None if no match
        reason: Human-readable reason for the routing decision
        priority_score: The priority score of the matched instance
        all_candidates: List of all candidate instances that matched context
    """
    matched_instance: Optional["AgentInstance"]
    reason: str
    priority_score: int = 0
    all_candidates: list = None

    def __post_init__(self):
        if self.all_candidates is None:
            self.all_candidates = []


class AgentRouter:
    """Agent router for multi-agent dispatching.

    This router:
    - Evaluates all enabled agent instances against the request context
    - Selects the highest priority matching instance
    - Provides fallback to default (None) when no instance matches

    Attributes:
        instance_manager: The agent instance manager to query
    """

    def __init__(self, instance_manager: "AgentInstanceManager"):
        """Initialize AgentRouter.

        Args:
            instance_manager: Agent instance manager for querying instances
        """
        self.instance_manager = instance_manager

    def _detect_intent(self, message: str) -> Optional[str]:
        """Detect user intent from message content.

        Args:
            message: User message content

        Returns:
            Detected agent type or None if no specific intent detected
        """
        if not message:
            return None

        message_lower = message.lower()
        message_keywords = set(message_lower.split())

        # Count keyword matches for each agent type
        matches = {}
        for agent_type, keywords in INTENT_KEYWORDS.items():
            count = 0
            for keyword in keywords:
                if keyword.lower() in message_lower:
                    count += 1
                # Also check word-level matches
                if keyword.lower() in message_keywords:
                    count += 1

            if count > 0:
                matches[agent_type] = count

        if not matches:
            return None

        # Return the agent type with most matches
        best_match = max(matches.items(), key=lambda x: x[1])
        logger.debug(f"Intent detection: {best_match[0]} with {best_match[1]} matches")
        return best_match[0]

    async def route_request(
        self,
        channel: str,
        user_id: str,
        message: Optional[str] = None,
    ) -> RoutingResult:
        """Route a request to the most appropriate agent instance.

        Args:
            channel: Channel name (e.g., "dingtalk", "feishu")
            user_id: User identifier
            message: Optional message content for intent-based routing

        Returns:
            RoutingResult with the matched instance and routing information
        """
        try:
            # Step 1: Try intent-based routing first (for specialized agents)
            # This allows technical questions to be routed to "expert" even if
            # a "general assistant" with GLOBAL scope exists
            if message:
                detected_intent = self._detect_intent(message)
                logger.info(f"[意图检测] 消息内容：{message[:50]}...")
                logger.info(f"[意图检测] 检测结果：{detected_intent}")

                if detected_intent:
                    # Find an agent instance matching the detected intent
                    all_instances = await self.instance_manager.list_instances(
                        enabled_only=True
                    )

                    # Look for instance with matching agent_type
                    for inst in all_instances:
                        if inst.agent_type == detected_intent and inst.enabled:
                            logger.info(
                                f"[意图路由] 找到匹配 agent - 名称:'{inst.name}' (type={detected_intent}, id={inst.id})"
                            )
                            return RoutingResult(
                                matched_instance=inst,
                                reason=f"Intent-based: Detected '{detected_intent}' from message, routed to '{inst.name}'",
                                priority_score=inst.get_priority_score(channel, user_id),
                                all_candidates=[inst],
                            )

            # Step 2: Fall back to context-based routing (scope-based)
            logger.info("[上下文路由] 开始上下文路由...")

            # Get all enabled instances
            all_instances = await self.instance_manager.list_instances(
                enabled_only=True
            )

            # Filter candidates by context (channel, user)
            candidates = [
                inst for inst in all_instances
                if inst.is_applicable_to(channel=channel, user_id=user_id)
            ]

            if not candidates:
                # No matching instance found
                logger.info("[上下文路由] 未找到匹配的 agent，使用默认 agent")
                return RoutingResult(
                    matched_instance=None,
                    reason="No matching agent instance found (context or intent)",
                    all_candidates=[],
                )

            # If no message for intent detection, use priority-based selection
            if not message:
                instance = await self.instance_manager.get_active_instance(
                    channel=channel,
                    user_id=user_id,
                )
                if instance is not None:
                    priority = instance.get_priority_score(channel=channel, user_id=user_id)
                    logger.info(f"[上下文路由] 候选 agent 列表:")
                    for i, cand in enumerate(candidates, 1):
                        logger.info(
                            f"  {i}. '{cand.name}' (scope={cand.scope.value}, priority={cand.get_priority_score(channel, user_id)})"
                        )
                    logger.info(
                        f"[上下文路由] 选中 agent: '{instance.name}' "
                        f"(scope={instance.scope.value}, priority={priority})"
                    )
                    return RoutingResult(
                        matched_instance=instance,
                        reason=f"Context-based: Matched agent '{instance.name}' with scope '{instance.scope.value}' (priority: {priority})",
                        priority_score=priority,
                        all_candidates=candidates,
                    )

            # With message: use intent to select among same-priority candidates
            # First, group candidates by priority score
            priority_groups: Dict[int, List[AgentInstance]] = {}
            for cand in candidates:
                score = cand.get_priority_score(channel=channel, user_id=user_id)
                if score not in priority_groups:
                    priority_groups[score] = []
                priority_groups[score].append(cand)

            # Get highest priority group
            max_priority = max(priority_groups.keys())
            top_candidates = priority_groups[max_priority]

            logger.info(f"[上下文路由] 候选 agent 列表 (最高优先级={max_priority}):")
            for i, cand in enumerate(top_candidates, 1):
                logger.info(
                    f"  {i}. '{cand.name}' (type={cand.agent_type}, scope={cand.scope.value})"
                )

            # If only one candidate at highest priority, select it
            if len(top_candidates) == 1:
                instance = top_candidates[0]
                logger.info(
                    f"[上下文路由] 选中 agent: '{instance.name}' "
                    f"(scope={instance.scope.value}, priority={max_priority})"
                )
                return RoutingResult(
                    matched_instance=instance,
                    reason=f"Context-based: Matched agent '{instance.name}' with scope '{instance.scope.value}' (priority: {max_priority})",
                    priority_score=max_priority,
                    all_candidates=candidates,
                )

            # Multiple candidates at same priority: use intent to select
            detected_intent = self._detect_intent(message) if message else None
            logger.info(f"[意图辅助路由] 检测结果：{detected_intent}")

            if detected_intent:
                # Look for candidate with matching agent_type
                for cand in top_candidates:
                    if cand.agent_type == detected_intent:
                        logger.info(
                            f"[意图辅助路由] 选中 agent: '{cand.name}' (type={cand.agent_type})"
                        )
                        return RoutingResult(
                            matched_instance=cand,
                            reason=f"Intent-assisted: Selected '{cand.name}' with matching type '{detected_intent}' (priority: {max_priority})",
                            priority_score=max_priority,
                            all_candidates=candidates,
                        )

                # No exact match, log that we'll use default selection
                logger.info(
                    f"[意图辅助路由] 无匹配的 agent_type，使用默认选择"
                )

            # Fall back to first candidate at highest priority
            instance = top_candidates[0]
            logger.info(
                f"[上下文路由] 选中 agent: '{instance.name}' "
                f"(scope={instance.scope.value}, priority={max_priority})"
            )
            return RoutingResult(
                matched_instance=instance,
                reason=f"Context-based: Matched agent '{instance.name}' with scope '{instance.scope.value}' (priority: {max_priority})",
                priority_score=max_priority,
                all_candidates=candidates,
            )

        except Exception as e:
            logger.error(f"Error during agent routing: {e}")
            return RoutingResult(
                matched_instance=None,
                reason=f"Error during routing: {e}",
            )

    async def get_routing_candidates(
        self,
        channel: str,
        user_id: str,
    ) -> list:
        """Get all agent instances that match the given context.

        Args:
            channel: Channel name
            user_id: User identifier

        Returns:
            List of matching agent instances, sorted by priority
        """
        all_instances = await self.instance_manager.list_instances(enabled_only=True)
        candidates = [
            (inst.get_priority_score(channel=channel, user_id=user_id), inst)
            for inst in all_instances
            if inst.is_applicable_to(channel=channel, user_id=user_id)
        ]
        candidates.sort(key=lambda x: x[0], reverse=True)
        return [inst for _, inst in candidates]


__all__ = ["AgentRouter", "RoutingResult"]
