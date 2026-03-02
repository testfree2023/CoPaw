# -*- coding: utf-8 -*-
"""Tests for TaskProcessor and TaskClassifier."""
import pytest
import asyncio
import tempfile
import shutil
from pathlib import Path

from copaw.app.runner.task_processor import TaskProcessor, TaskClassifier
from copaw.app.runner.task_queue import TaskQueue
from copaw.app.runner.task_models import TaskSpec, TaskType, TaskStatus


@pytest.fixture
def temp_tasks_dir():
    """Create temporary directory for task files."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def task_queue(temp_tasks_dir):
    """Create TaskQueue with temporary storage."""
    return TaskQueue(save_dir=temp_tasks_dir)


@pytest.fixture
def task_processor(task_queue):
    """Create TaskProcessor instance."""
    return TaskProcessor(task_queue=task_queue)


class TestTaskClassifier:
    """Test TaskClassifier class."""

    def test_classify_instruction_chinese(self):
        """Test classifying Chinese instructions."""
        assert TaskClassifier.classify("创建一个定时任务") == TaskType.INSTRUCTION
        assert TaskClassifier.classify("删除这个文件") == TaskType.INSTRUCTION
        assert TaskClassifier.classify("发送邮件") == TaskType.INSTRUCTION

    def test_classify_instruction_english(self):
        """Test classifying English instructions."""
        assert TaskClassifier.classify("Create a cron job") == TaskType.INSTRUCTION
        assert TaskClassifier.classify("Delete this file") == TaskType.INSTRUCTION
        assert TaskClassifier.classify("Send email") == TaskType.INSTRUCTION

    def test_classify_rule_chinese(self):
        """Test classifying Chinese rules."""
        assert TaskClassifier.classify("记住总是用中文回复") == TaskType.RULE
        assert TaskClassifier.classify("必须每天给我发报告") == TaskType.RULE
        assert TaskClassifier.classify("不要发送敏感信息") == TaskType.RULE

    def test_classify_rule_english(self):
        """Test classifying English rules."""
        assert TaskClassifier.classify("Remember to always use English") == TaskType.RULE
        assert TaskClassifier.classify("Never send sensitive data") == TaskType.RULE
        assert TaskClassifier.classify("Always verify before sending") == TaskType.RULE

    def test_classify_conversation(self):
        """Test classifying conversations."""
        assert TaskClassifier.classify("你好") == TaskType.CONVERSATION
        assert TaskClassifier.classify("今天天气怎么样") == TaskType.CONVERSATION
        assert TaskClassifier.classify("How are you?") == TaskType.CONVERSATION

    def test_rule_priority_over_instruction(self):
        """Test that rules have higher priority than instructions."""
        # "记住创建" contains both rule and instruction keywords
        # Rule should win
        assert TaskClassifier.classify("记住创建任务") == TaskType.RULE

    def test_extract_rule_content_patterns(self):
        """Test extracting rule content from various patterns."""
        # Chinese patterns
        assert TaskClassifier.extract_rule_content("记住，总是用中文") == "总是用中文"
        assert TaskClassifier.extract_rule_content("记得每天都要喝水") == "每天都要喝水"
        assert TaskClassifier.extract_rule_content("总是使用正式语言") == "使用正式语言"
        assert TaskClassifier.extract_rule_content("不要发送敏感信息") == "发送敏感信息"

        # English patterns
        assert TaskClassifier.extract_rule_content("Remember, always be kind") == "always be kind"
        assert TaskClassifier.extract_rule_content("Always use proper grammar") == "use proper grammar"
        assert TaskClassifier.extract_rule_content("Never share passwords") == "share passwords"

    def test_extract_rule_content_fallback(self):
        """Test fallback to original query."""
        # If no pattern matches, return original
        result = TaskClassifier.extract_rule_content("这是一条规则")
        assert result == "这是一条规则"


class TestTaskProcessor:
    """Test TaskProcessor class."""

    @pytest.mark.asyncio
    async def test_process_instruction(self, task_processor, task_queue):
        """Test processing an instruction task."""
        task = TaskSpec(
            user_id="user123",
            channel="dingtalk",
            session_id="session1",
            type=TaskType.INSTRUCTION,
            query="创建一个定时任务",
        )
        await task_queue.enqueue(task)

        # Process the task
        dequeued = await task_queue.dequeue()
        await task_processor.process_task(dequeued)

        # Task should be completed (or waiting verification)
        completed_task = await task_queue.get_task(dequeued.id)
        assert completed_task is not None
        assert completed_task.status in [
            TaskStatus.COMPLETED,
            TaskStatus.WAITING_VERIFICATION,
        ]

    @pytest.mark.asyncio
    async def test_process_rule(self, task_processor, task_queue):
        """Test processing a rule task."""
        task = TaskSpec(
            user_id="user123",
            channel="dingtalk",
            session_id="session1",
            type=TaskType.RULE,
            query="记住，总是用中文回复",
        )
        await task_queue.enqueue(task)

        # Process the task
        dequeued = await task_queue.dequeue()
        await task_processor.process_task(dequeued)

        # Task should be completed
        completed_task = await task_queue.get_task(dequeued.id)
        assert completed_task is not None
        assert completed_task.status == TaskStatus.COMPLETED
        assert "规则已保存" in completed_task.llm_response

    @pytest.mark.asyncio
    async def test_process_conversation(self, task_processor, task_queue):
        """Test processing a conversation task."""
        task = TaskSpec(
            user_id="user123",
            channel="dingtalk",
            session_id="session1",
            type=TaskType.CONVERSATION,
            query="你好",
        )
        await task_queue.enqueue(task)

        # Process the task
        dequeued = await task_queue.dequeue()
        await task_processor.process_task(dequeued)

        # Task should be completed
        completed_task = await task_queue.get_task(dequeued.id)
        assert completed_task is not None
        assert completed_task.status == TaskStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_auto_classification(self, task_processor, task_queue):
        """Test automatic task type classification."""
        # Create task without type
        task = TaskSpec(
            user_id="user123",
            channel="dingtalk",
            session_id="session1",
            type=None,  # Not classified
            query="创建一个新的定时任务",
        )
        await task_queue.enqueue(task)

        # Process - should auto-classify as INSTRUCTION
        dequeued = await task_queue.dequeue()
        await task_processor.process_task(dequeued)

        completed_task = await task_queue.get_task(dequeued.id)
        assert completed_task.type == TaskType.INSTRUCTION

    @pytest.mark.asyncio
    async def test_start_stop(self, task_processor):
        """Test starting and stopping the processor."""
        # Start
        await task_processor.start()
        assert task_processor._running is True
        assert task_processor._worker_task is not None

        # Stop
        await task_processor.stop()
        assert task_processor._running is False

    @pytest.mark.asyncio
    async def test_processor_loop(self, task_queue):
        """Test the processor main loop."""
        processor = TaskProcessor(task_queue=task_queue)
        await processor.start()

        # Add a task
        task = TaskSpec(
            user_id="user123",
            channel="dingtalk",
            session_id="session1",
            type=TaskType.CONVERSATION,
            query="Hello",
        )
        await task_queue.enqueue(task)

        # Wait for processing
        await asyncio.sleep(0.5)

        # Stop
        await processor.stop()

        # Task should be processed
        completed = await task_queue.list_completed()
        assert len(completed) > 0

    @pytest.mark.asyncio
    async def test_verify_cron_task_success(self, task_processor):
        """Test cron task verification with success."""
        task = TaskSpec(
            user_id="user123",
            channel="dingtalk",
            session_id="session1",
            type=TaskType.INSTRUCTION,
            query="Create a cron job",
        )
        response = "Job created successfully with job_id: 12345"

        verified, details = await task_processor._verify_cron_task(response)
        assert verified is True

    @pytest.mark.asyncio
    async def test_verify_cron_task_failure(self, task_processor):
        """Test cron task verification with failure."""
        task = TaskSpec(
            user_id="user123",
            channel="dingtalk",
            session_id="session1",
            type=TaskType.INSTRUCTION,
            query="Create a cron job",
        )
        response = "I don't understand"

        verified, details = await task_processor._verify_cron_task(response)
        assert verified is False
        assert "does not indicate" in details

    @pytest.mark.asyncio
    async def test_verify_file_operation_success(self, task_processor):
        """Test file operation verification with success."""
        task = TaskSpec(
            user_id="user123",
            channel="dingtalk",
            session_id="session1",
            type=TaskType.INSTRUCTION,
            query="Write to file",
        )
        response = "File written successfully"

        verified, details = await task_processor._verify_file_operation(task.query, response)
        assert verified is True

    @pytest.mark.asyncio
    async def test_verify_file_operation_failure(self, task_processor):
        """Test file operation verification with failure."""
        task = TaskSpec(
            user_id="user123",
            channel="dingtalk",
            session_id="session1",
            type=TaskType.INSTRUCTION,
            query="Write to file",
        )
        response = "Error occurred"

        verified, details = await task_processor._verify_file_operation(task.query, response)
        assert verified is False


class TestTaskClassifierEdgeCases:
    """Test edge cases for TaskClassifier."""

    def test_empty_query(self):
        """Test classifying empty query."""
        assert TaskClassifier.classify("") == TaskType.CONVERSATION

    def test_mixed_case_english(self):
        """Test case-insensitive English classification."""
        assert TaskClassifier.classify("CREATE a task") == TaskType.INSTRUCTION
        assert TaskClassifier.classify("Remember TO Always") == TaskType.RULE

    def test_punctuation_in_rule(self):
        """Test rule extraction with punctuation."""
        assert TaskClassifier.extract_rule_content("记住：总是用中文") == "总是用中文"
        assert TaskClassifier.extract_rule_content("Remember: be kind") == "be kind"

    def test_whitespace_handling(self):
        """Test whitespace handling in rule extraction."""
        assert TaskClassifier.extract_rule_content("  记住，总是用中文  ") == "总是用中文"
        assert TaskClassifier.extract_rule_content("  Remember, be kind  ") == "be kind"
