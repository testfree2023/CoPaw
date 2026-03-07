/**
 * Task Detail Drawer Component
 */
import React from 'react';
import { Drawer, Descriptions, Tag, Button, Space, Divider, Alert, Typography } from 'antd';
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  ClockCircleOutlined,
  ReloadOutlined,
  DeleteOutlined,
} from '@ant-design/icons';
import type { TaskSpec } from '../../../../api/types/task';
import type { DrawerProps } from 'antd';

const { Text, Paragraph } = Typography;

interface TaskDrawerProps extends Omit<DrawerProps, 'children'> {
  task: TaskSpec;
  onRetry?: () => void;
  onDelete?: () => void;
}

/**
 * Get status tag with icon
 */
const getStatusTag = (status: string) => {
  const config: Record<string, { color: string; icon: React.ReactNode; text: string }> = {
    pending: {
      color: 'blue',
      icon: <ClockCircleOutlined />,
      text: '待处理',
    },
    processing: {
      color: 'purple',
      icon: <ClockCircleOutlined />,
      text: '处理中',
    },
    waiting_verification: {
      color: 'orange',
      icon: <ClockCircleOutlined />,
      text: '待验证',
    },
    completed: {
      color: 'green',
      icon: <CheckCircleOutlined />,
      text: '已完成',
    },
    failed: {
      color: 'red',
      icon: <CloseCircleOutlined />,
      text: '失败',
    },
    reprocessing: {
      color: 'cyan',
      icon: <ReloadOutlined />,
      text: '重新处理中',
    },
  };

  const cfg = config[status] || { color: 'default', icon: null, text: status };
  return <Tag color={cfg.color}>{cfg.icon} {cfg.text}</Tag>;
};

/**
 * Get type tag
 */
const getTypeTag = (type: string) => {
  const config: Record<string, { color: string; text: string }> = {
    instruction: { color: 'geekblue', text: '指令' },
    rule: { color: 'volcano', text: '规则' },
    conversation: { color: 'lime', text: '对话' },
  };

  const cfg = config[type] || { color: 'default', text: type };
  return <Tag color={cfg.color}>{cfg.text}</Tag>;
};

/**
 * Task Detail Drawer
 */
const TaskDrawer: React.FC<TaskDrawerProps> = ({ task, onRetry, onDelete, ...drawerProps }) => {
  return (
    <Drawer
      title="任务详情"
      width={720}
      {...drawerProps}
    >
      <Space direction="vertical" style={{ width: '100%' }} size="large">
        {/* Status and Type */}
        <Space>
          {getStatusTag(task.status)}
          {getTypeTag(task.type)}
        </Space>

        {/* Basic Info */}
        <Descriptions
          title="基本信息"
          column={1}
          bordered
          size="small"
        >
          <Descriptions.Item label="任务 ID">
            <Text code>{task.id}</Text>
          </Descriptions.Item>
          <Descriptions.Item label="查询内容">
            <Paragraph copyable>{task.query}</Paragraph>
          </Descriptions.Item>
          <Descriptions.Item label="用户 ID">
            <Text code>{task.user_id}</Text>
          </Descriptions.Item>
          <Descriptions.Item label="渠道">
            <Tag>{task.channel}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="会话 ID">
            <Text code>{task.session_id}</Text>
          </Descriptions.Item>
          <Descriptions.Item label="重试次数">
            {task.retry_count} / {task.max_retries}
          </Descriptions.Item>
        </Descriptions>

        {/* Timestamps */}
        <Descriptions
          title="时间信息"
          column={2}
          bordered
          size="small"
        >
          <Descriptions.Item label="创建时间">
            {new Date(task.created_at).toLocaleString('zh-CN')}
          </Descriptions.Item>
          <Descriptions.Item label="开始时间">
            {task.started_at
              ? new Date(task.started_at).toLocaleString('zh-CN')
              : '-'}
          </Descriptions.Item>
          <Descriptions.Item label="完成时间">
            {task.completed_at
              ? new Date(task.completed_at).toLocaleString('zh-CN')
              : '-'}
          </Descriptions.Item>
        </Descriptions>

        {/* LLM Response */}
        {task.llm_response && (
          <>
            <Divider orientation="left">LLM 响应</Divider>
            <Paragraph
              style={{
                backgroundColor: '#f6ffed',
                border: '1px solid #b7eb8f',
                padding: 12,
                borderRadius: 4,
              }}
            >
              {task.llm_response}
            </Paragraph>
          </>
        )}

        {/* Verification Result */}
        {task.verification_result !== undefined && (
          <>
            <Divider orientation="left">验证结果</Divider>
            {task.verification_result ? (
              <Alert
                message="验证通过"
                description={task.verification_details || '任务执行成功并通过验证'}
                type="success"
                showIcon
              />
            ) : (
              <Alert
                message="验证失败"
                description={task.verification_details || '任务执行结果未通过验证'}
                type="error"
                showIcon
              />
            )}
          </>
        )}

        {/* Error Info */}
        {task.last_error && (
          <>
            <Divider orientation="left">错误信息</Divider>
            <Alert
              message="错误"
              description={task.last_error}
              type="error"
              showIcon
            />
          </>
        )}

        {/* Metadata */}
        {task.metadata && Object.keys(task.metadata).length > 0 && (
          <>
            <Divider orientation="left">元数据</Divider>
            <pre
              style={{
                backgroundColor: '#f5f5f5',
                padding: 12,
                borderRadius: 4,
                overflow: 'auto',
                maxHeight: 200,
              }}
            >
              {JSON.stringify(task.metadata, null, 2)}
            </pre>
          </>
        )}

        {/* Actions */}
        <Divider orientation="left">操作</Divider>
        <Space>
          {task.status === 'failed' && task.retry_count < task.max_retries && (
            <Button
              type="primary"
              icon={<ReloadOutlined />}
              onClick={onRetry}
            >
              重试任务
            </Button>
          )}
          {(task.status === 'completed' || task.status === 'failed') && (
            <Button
              danger
              icon={<DeleteOutlined />}
              onClick={onDelete}
            >
              删除任务
            </Button>
          )}
        </Space>
      </Space>
    </Drawer>
  );
};

export default TaskDrawer;
