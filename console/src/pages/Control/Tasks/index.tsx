/**
 * Tasks Page - Task Management for CoPaw
 */
import React, { useState, useEffect } from 'react';
import { Table, Card, Button, Tag, Space, Input, Select, Popconfirm, message, Badge } from 'antd';
import {
  SearchOutlined,
  PlusOutlined,
  ReloadOutlined,
  DeleteOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { taskApi, type TaskListItem, type TaskSpec } from '@/api/modules/task';
import styles from './index.module.less';
import TaskDrawer from './components/TaskDrawer';
import CreateTaskModal from './components/CreateTaskModal';

const { Option } = Select;

/**
 * Tasks Page Component
 */
const TasksPage: React.FC = () => {
  const [tasks, setTasks] = useState<TaskListItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedTask, setSelectedTask] = useState<TaskSpec | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [createModalOpen, setCreateModalOpen] = useState(false);

  // Filters
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [typeFilter, setTypeFilter] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');

  // Summary stats
  const [summary, setSummary] = useState<{
    total: number;
    by_status: Record<string, number>;
    by_type: Record<string, number>;
  } | null>(null);

  /**
   * Load tasks from API
   */
  const loadTasks = async () => {
    setLoading(true);
    try {
      const params: Record<string, string> = {};
      if (statusFilter !== 'all') params.status = statusFilter;
      if (typeFilter !== 'all') params.task_type = typeFilter;
      params.limit = '100';

      const data = await taskApi.listTasks(params);
      setTasks(data);
    } catch (error) {
      console.error('Failed to load tasks:', error);
      message.error('加载任务列表失败');
    } finally {
      setLoading(false);
    }
  };

  /**
   * Load task summary stats
   */
  const loadSummary = async () => {
    try {
      const data = await taskApi.getTaskSummary();
      setSummary(data);
    } catch (error) {
      console.error('Failed to load summary:', error);
    }
  };

  useEffect(() => {
    loadTasks();
    loadSummary();
  }, [statusFilter, typeFilter]);

  /**
   * Handle task click to open drawer
   */
  const handleTaskClick = async (taskId: string) => {
    try {
      const task = await taskApi.getTask(taskId);
      setSelectedTask(task);
      setDrawerOpen(true);
    } catch (error) {
      console.error('Failed to load task details:', error);
      message.error('加载任务详情失败');
    }
  };

  /**
   * Handle retry task
   */
  const handleRetry = async (taskId: string) => {
    try {
      await taskApi.retryTask(taskId);
      message.success('任务已重新排队');
      loadTasks();
      loadSummary();
    } catch (error) {
      console.error('Failed to retry task:', error);
      message.error('重试任务失败');
    }
  };

  /**
   * Handle delete task
   */
  const handleDelete = async (taskId: string) => {
    try {
      await taskApi.deleteTask(taskId);
      message.success('任务已删除');
      loadTasks();
      loadSummary();
    } catch (error) {
      console.error('Failed to delete task:', error);
      message.error('删除任务失败');
    }
  };

  /**
   * Get status tag color
   */
  const getStatusColor = (status: string): string => {
    const colors: Record<string, string> = {
      pending: 'blue',
      processing: 'purple',
      waiting_verification: 'orange',
      completed: 'green',
      failed: 'red',
      reprocessing: 'cyan',
    };
    return colors[status] || 'default';
  };

  /**
   * Get type tag color
   */
  const getTypeColor = (type: string): string => {
    const colors: Record<string, string> = {
      instruction: 'geekblue',
      rule: 'volcano',
      conversation: 'lime',
    };
    return colors[type] || 'default';
  };

  /**
   * Table columns definition
   */
  const columns: ColumnsType<TaskListItem> = [
    {
      title: 'ID',
      dataIndex: 'id',
      key: 'id',
      width: 280,
      ellipsis: true,
      render: (id: string) => <code>{id.slice(0, 8)}...</code>,
    },
    {
      title: '类型',
      dataIndex: 'type',
      key: 'type',
      width: 100,
      render: (type: string) => (
        <Tag color={getTypeColor(type)}>
          {type === 'instruction' && '指令'}
          {type === 'rule' && '规则'}
          {type === 'conversation' && '对话'}
        </Tag>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 120,
      render: (status: string) => (
        <Tag color={getStatusColor(status)}>{status}</Tag>
      ),
    },
    {
      title: '查询内容',
      dataIndex: 'query',
      key: 'query',
      ellipsis: true,
      render: (query: string) => (
        <span style={{ maxWidth: 300, display: 'inline-block', overflow: 'hidden', textOverflow: 'ellipsis' }}>
          {query}
        </span>
      ),
    },
    {
      title: '验证结果',
      dataIndex: 'verification_result',
      key: 'verification_result',
      width: 100,
      render: (result?: boolean) => {
        if (result === undefined || result === null) return '-';
        return result ? (
          <CheckCircleOutlined style={{ color: '#52c41a' }} />
        ) : (
          <CloseCircleOutlined style={{ color: '#ff4d4f' }} />
        );
      },
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      render: (createdAt: string) => new Date(createdAt).toLocaleString('zh-CN'),
    },
    {
      title: '操作',
      key: 'action',
      width: 150,
      render: (_, record) => (
        <Space size="small">
          <Button
            type="link"
            size="small"
            onClick={() => handleTaskClick(record.id)}
          >
            详情
          </Button>
          {record.status === 'failed' && (
            <Button
              type="link"
              size="small"
              onClick={() => handleRetry(record.id)}
            >
              重试
            </Button>
          )}
          {(record.status === 'completed' || record.status === 'failed') && (
            <Popconfirm
              title="确定要删除此任务吗？"
              onConfirm={() => handleDelete(record.id)}
              okText="确定"
              cancelText="取消"
            >
              <Button type="link" size="small" danger>
                <DeleteOutlined />
              </Button>
            </Popconfirm>
          )}
        </Space>
      ),
    },
  ];

  // Filter tasks by search query
  const filteredTasks = tasks.filter((task) =>
    task.query.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className={styles.tasksPage}>
      <Card className={styles.filterCard}>
        <Space wrap size="middle" style={{ width: '100%', justifyContent: 'space-between' }}>
          <Space wrap>
            <Select
              value={statusFilter}
              onChange={setStatusFilter}
              style={{ width: 150 }}
              placeholder="状态筛选"
            >
              <Option value="all">全部状态</Option>
              <Option value="pending">待处理</Option>
              <Option value="processing">处理中</Option>
              <Option value="waiting_verification">待验证</Option>
              <Option value="completed">已完成</Option>
              <Option value="failed">失败</Option>
            </Select>

            <Select
              value={typeFilter}
              onChange={setTypeFilter}
              style={{ width: 120 }}
              placeholder="类型筛选"
            >
              <Option value="all">全部类型</Option>
              <Option value="instruction">指令</Option>
              <Option value="rule">规则</Option>
              <Option value="conversation">对话</Option>
            </Select>

            <Input
              placeholder="搜索查询内容..."
              prefix={<SearchOutlined />}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{ width: 250 }}
            />
          </Space>

          <Space>
            <Button
              icon={<ReloadOutlined />}
              onClick={loadTasks}
              loading={loading}
            >
              刷新
            </Button>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => setCreateModalOpen(true)}
            >
              创建任务
            </Button>
          </Space>
        </Space>
      </Card>

      {summary && (
        <Card className={styles.summaryCard} size="small">
          <Space wrap size="large">
            <div>
              <Badge count={summary.total} overflowCount={999} size="default" />
              <span style={{ marginLeft: 8 }}>总任务数</span>
            </div>
            <div>
              <Badge
                count={summary.by_status.pending || 0}
                color="blue"
                size="default"
              />
              <span style={{ marginLeft: 8 }}>待处理</span>
            </div>
            <div>
              <Badge
                count={summary.by_status.processing || 0}
                color="purple"
                size="default"
              />
              <span style={{ marginLeft: 8 }}>处理中</span>
            </div>
            <div>
              <Badge
                count={summary.by_status.completed || 0}
                color="green"
                size="default"
              />
              <span style={{ marginLeft: 8 }}>已完成</span>
            </div>
            <div>
              <Badge
                count={summary.by_status.failed || 0}
                color="red"
                size="default"
              />
              <span style={{ marginLeft: 8 }}>失败</span>
            </div>
          </Space>
        </Card>
      )}

      <Card className={styles.tableCard}>
        <Table
          columns={columns}
          dataSource={filteredTasks}
          loading={loading}
          rowKey="id"
          pagination={{
            pageSize: 20,
            showSizeChanger: true,
            showTotal: (total) => `共 ${total} 个任务`,
          }}
        />
      </Card>

      {/* Task Detail Drawer */}
      {selectedTask && (
        <TaskDrawer
          task={selectedTask}
          open={drawerOpen}
          onClose={() => {
            setDrawerOpen(false);
            setSelectedTask(null);
          }}
          onRetry={() => handleRetry(selectedTask.id)}
          onDelete={() => handleDelete(selectedTask.id)}
        />
      )}

      {/* Create Task Modal */}
      <CreateTaskModal
        open={createModalOpen}
        onCancel={() => setCreateModalOpen(false)}
        onSuccess={() => {
          setCreateModalOpen(false);
          loadTasks();
        }}
      />
    </div>
  );
};

export default TasksPage;
