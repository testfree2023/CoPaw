# -*- coding: utf-8 -*-
"""Task Templates for CoPaw.

This module provides pre-defined task templates for common scenarios,
allowing users to quickly create structured tasks.

Templates include:
- Cron/Schedule management
- File operations
- Email processing
- News digest
- Data organization
"""
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from enum import Enum

from .task_models import TaskType


class TemplateCategory(str, Enum):
    """Template categories."""
    CRON = "cron"
    FILE = "file"
    EMAIL = "email"
    NEWS = "news"
    ORGANIZATION = "organization"
    CUSTOM = "custom"


@dataclass
class TaskTemplate:
    """A pre-defined task template.

    Attributes:
        id: Unique template identifier
        name: Display name
        description: Template description
        category: Template category
        query_template: Query template with {placeholders}
        default_metadata: Default metadata values
        placeholders: List of placeholder names that user needs to fill
    """
    id: str
    name: str
    description: str
    category: TemplateCategory
    query_template: str
    default_metadata: Dict[str, Any] = field(default_factory=dict)
    placeholders: List[str] = field(default_factory=list)
    icon: str = "FileText"  # Icon name for UI


# Pre-defined templates
CRON_TEMPLATES = [
    TaskTemplate(
        id="cron_daily_reminder",
        name="每日提醒",
        description="创建一个每天固定时间的提醒",
        category=TemplateCategory.CRON,
        query_template="创建一个每天 {time} 的提醒，内容是 {content}",
        placeholders=["time", "content"],
        default_metadata={"reminder_type": "daily"},
        icon="CalendarClock",
    ),
    TaskTemplate(
        id="cron_weekly_report",
        name="周报生成",
        description="创建每周自动生成长报的任务",
        category=TemplateCategory.CRON,
        query_template="每周五下午 {time} 生成本周工作周报",
        placeholders=["time"],
        default_metadata={"report_type": "weekly"},
        icon="FileText",
    ),
    TaskTemplate(
        id="cron_cleanup",
        name="定期清理",
        description="定期清理临时文件",
        category=TemplateCategory.CRON,
        query_template="每天 {time} 清理 {directory} 目录下的临时文件",
        placeholders=["time", "directory"],
        default_metadata={"cleanup_type": "temp_files"},
        icon="Trash2",
    ),
]

FILE_TEMPLATES = [
    TaskTemplate(
        id="file_organize",
        name="文件整理",
        description="整理指定目录下的文件",
        category=TemplateCategory.FILE,
        query_template="整理 {directory} 目录，按文件类型分类到不同子文件夹",
        placeholders=["directory"],
        default_metadata={"operation": "organize"},
        icon="Folder",
    ),
    TaskTemplate(
        id="file_backup",
        name="文件备份",
        description="备份指定目录到备份位置",
        category=TemplateCategory.FILE,
        query_template="将 {source} 目录备份到 {destination}",
        placeholders=["source", "destination"],
        default_metadata={"operation": "backup"},
        icon="HardDrive",
    ),
    TaskTemplate(
        id="file_rename",
        name="批量重命名",
        description="批量重命名文件",
        category=TemplateCategory.FILE,
        query_template="将 {directory} 目录下的文件按 {pattern} 格式重命名",
        placeholders=["directory", "pattern"],
        default_metadata={"operation": "rename"},
        icon="Edit",
    ),
]

EMAIL_TEMPLATES = [
    TaskTemplate(
        id="email_digest",
        name="邮件摘要",
        description="生成未读邮件的摘要",
        category=TemplateCategory.EMAIL,
        query_template="读取我的未读邮件，生成一个摘要报告",
        placeholders=[],
        default_metadata={"email_type": "unread_digest"},
        icon="Mail",
    ),
    TaskTemplate(
        id="email_auto_reply",
        name="自动回复",
        description="设置自动回复规则",
        category=TemplateCategory.EMAIL,
        query_template="对于来自 {sender} 的邮件，自动回复 {reply_content}",
        placeholders=["sender", "reply_content"],
        default_metadata={"email_type": "auto_reply"},
        icon="Send",
    ),
]

NEWS_TEMPLATES = [
    TaskTemplate(
        id="news_daily_digest",
        name="每日新闻摘要",
        description="获取每日热门新闻",
        category=TemplateCategory.NEWS,
        query_template="获取今天的热门新闻，包括 {topics} 领域",
        placeholders=["topics"],
        default_metadata={"news_type": "daily_digest"},
        icon="Globe",
    ),
    TaskTemplate(
        id="tech_news",
        name="科技新闻追踪",
        description="追踪特定科技主题的新闻",
        category=TemplateCategory.NEWS,
        query_template="追踪关于 {topic} 的最新科技新闻",
        placeholders=["topic"],
        default_metadata={"news_type": "tech_tracker"},
        icon="Cpu",
    ),
]

ORGANIZATION_TEMPLATES = [
    TaskTemplate(
        id="organize_contacts",
        name="联系人整理",
        description="整理和去重联系人",
        category=TemplateCategory.ORGANIZATION,
        query_template="整理我的联系人列表，合并重复项并补充缺失信息",
        placeholders=[],
        default_metadata={"org_type": "contacts"},
        icon="Users",
    ),
    TaskTemplate(
        id="organize_calendar",
        name="日程整理",
        description="整理 upcoming 日程安排",
        category=TemplateCategory.ORGANIZATION,
        query_template="整理我下周的日程安排，找出冲突并给出建议",
        placeholders=[],
        default_metadata={"org_type": "calendar"},
        icon="Calendar",
    ),
]

# All templates combined
ALL_TEMPLATES: List[TaskTemplate] = (
    CRON_TEMPLATES +
    FILE_TEMPLATES +
    EMAIL_TEMPLATES +
    NEWS_TEMPLATES +
    ORGANIZATION_TEMPLATES
)


def get_template_by_id(template_id: str) -> Optional[TaskTemplate]:
    """Get a template by its ID.

    Args:
        template_id: The template identifier

    Returns:
        The template if found, None otherwise
    """
    for template in ALL_TEMPLATES:
        if template.id == template_id:
            return template
    return None


def get_templates_by_category(category: TemplateCategory) -> List[TaskTemplate]:
    """Get all templates for a category.

    Args:
        category: The template category

    Returns:
        List of templates in the category
    """
    return [t for t in ALL_TEMPLATES if t.category == category]


def build_query_from_template(
    template: TaskTemplate,
    values: Dict[str, str]
) -> str:
    """Build a query string from a template and placeholder values.

    Args:
        template: The task template
        values: Dictionary of placeholder names to values

    Returns:
        The filled query string
    """
    query = template.query_template
    for key, value in values.items():
        query = query.replace(f"{{{key}}}", str(value))
    return query


def get_template_list_for_api() -> List[Dict[str, Any]]:
    """Get template list in API response format.

    Returns:
        List of template dictionaries for API responses
    """
    return [
        {
            "id": t.id,
            "name": t.name,
            "description": t.description,
            "category": t.category.value,
            "icon": t.icon,
            "placeholders": t.placeholders,
        }
        for t in ALL_TEMPLATES
    ]
