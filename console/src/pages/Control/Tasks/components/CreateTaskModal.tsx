/**
 * Create Task Modal Component with Template Support
 */
import React, { useState, useEffect } from 'react';
import { Modal, Form, Input, Select, message, Tabs, Card, Space, Tag, Button } from 'antd';
import { PlusOutlined, ThunderboltOutlined } from '@ant-design/icons';
import { taskApi, type CreateTaskRequest } from '@/api/modules/task';

const { TextArea } = Input;
const { Option } = Select;

interface Template {
  id: string;
  name: string;
  description: string;
  category: string;
  icon: string;
  placeholders: string[];
}

interface CreateTaskModalProps {
  open: boolean;
  onCancel: () => void;
  onSuccess: () => void;
  defaultUserId?: string;
  defaultSessionId?: string;
  defaultChannel?: string;
}

/**
 * Create Task Modal with template support
 */
const CreateTaskModal: React.FC<CreateTaskModalProps> = ({
  open,
  onCancel,
  onSuccess,
  defaultUserId = 'console-user',
  defaultSessionId = 'console-session',
  defaultChannel = 'console',
}) => {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [selectedTemplate, setSelectedTemplate] = useState<Template | null>(null);
  const [activeCategory, setActiveCategory] = useState<string>('all');

  // Load templates on modal open
  useEffect(() => {
    if (open) {
      loadTemplates();
    }
  }, [open]);

  const loadTemplates = async () => {
    try {
      const response = await taskApi.listTemplates();
      setTemplates(response.templates || []);
    } catch (error) {
      console.error('Failed to load templates:', error);
    }
  };

  const handleTemplateSelect = (template: Template) => {
    setSelectedTemplate(template);

    // Fill the query with template's default text
    if (template.placeholders.length === 0) {
      // No placeholders, use the template directly
      const templateQueries: Record<string, string> = {
        cron_daily_reminder: '创建一个每天固定时间的提醒',
        cron_weekly_report: '每周五下午生成本周工作周报',
        cron_cleanup: '每天清理临时文件目录',
        file_organize: '整理目录，按文件类型分类到不同子文件夹',
        file_backup: '将源目录备份到目标位置',
        file_rename: '批量重命名文件',
        email_digest: '读取未读邮件并生成摘要报告',
        email_auto_reply: '设置自动回复规则',
        news_daily_digest: '获取今天的热门新闻',
        tech_news: '追踪最新科技新闻',
        organize_contacts: '整理联系人列表，合并重复项',
        organize_calendar: '整理下周的日程安排',
      };
      form.setFieldValue('query', templateQueries[template.id] || template.name);
    } else {
      // Has placeholders, show template with placeholders
      const templateWithPlaceholders: Record<string, string> = {
        cron_daily_reminder: "创建一个每天 {time} 的提醒，内容是 {content}",
        cron_weekly_report: "每周五下午 {time} 生成本周工作周报",
        cron_cleanup: "每天 {time} 清理 {directory} 目录下的临时文件",
        file_organize: "整理 {directory} 目录，按文件类型分类到不同子文件夹",
        file_backup: "将 {source} 目录备份到 {destination}",
        file_rename: "将 {directory} 目录下的文件按 {pattern} 格式重命名",
        email_digest: "读取我的未读邮件，生成一个摘要报告",
        email_auto_reply: "对于来自 {sender} 的邮件，自动回复 {reply_content}",
        news_daily_digest: "获取今天的热门新闻，包括 {topics} 领域",
        tech_news: "追踪关于 {topic} 的最新科技新闻",
        organize_contacts: "整理我的联系人列表，合并重复项并补充缺失信息",
        organize_calendar: "整理我下周的日程安排，找出冲突并给出建议",
      };
      form.setFieldValue('query', templateWithPlaceholders[template.id] || template.name);
    }
    form.setFieldValue('task_type', 'instruction');
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      setLoading(true);

      const request: CreateTaskRequest = {
        user_id: defaultUserId,
        channel: defaultChannel,
        session_id: defaultSessionId,
        query: values.query,
        task_type: values.task_type as 'instruction' | 'rule' | 'conversation',
        metadata: selectedTemplate ? {
          template_id: selectedTemplate.id,
          template_category: selectedTemplate.category,
        } : {},
      };

      await taskApi.createTask(request);
      message.success('任务创建成功！');
      form.resetFields();
      setSelectedTemplate(null);
      onSuccess();
    } catch (error: any) {
      if (error.response) {
        message.error(`创建失败：${error.response.data.detail || error.message}`);
      } else if (error !== false) {
        console.error('Failed to create task:', error);
        message.error('创建失败，请重试');
      }
    } finally {
      setLoading(false);
    }
  };

  const categoryTabs = [
    { key: 'all', label: '全部', icon: '📋' },
    { key: 'cron', label: '日程管理', icon: '📅' },
    { key: 'file', label: '文件操作', icon: '📁' },
    { key: 'email', label: '邮件处理', icon: '✉️' },
    { key: 'news', label: '新闻资讯', icon: '📰' },
    { key: 'organization', label: '整理归纳', icon: '🗂️' },
  ];

  const filteredTemplates = activeCategory === 'all'
    ? templates
    : templates.filter(t => t.category === activeCategory);

  return (
    <Modal
      title={
        <span>
          <PlusOutlined style={{ marginRight: 8 }} />
          创建任务
        </span>
      }
      open={open}
      onCancel={onCancel}
      onOk={handleSubmit}
      confirmLoading={loading}
      width={750}
      footer={[
        <Button key="cancel" onClick={onCancel}>
          取消
        </Button>,
        <Button
          key="submit"
          type="primary"
          onClick={handleSubmit}
          loading={loading}
          icon={<ThunderboltOutlined />}
        >
          创建任务
        </Button>,
      ]}
    >
      <div style={{ marginBottom: 16 }}>
        <Space direction="vertical" style={{ width: '100%' }} size="large">
          {/* Template Selector */}
          <div>
            <label style={{ display: 'block', marginBottom: 8, fontWeight: 500 }}>
              🎯 快速模板
            </label>
            <Tabs
              activeKey={activeCategory}
              onChange={setActiveCategory}
              items={categoryTabs.map(tab => ({
                key: tab.key,
                label: `${tab.icon} ${tab.label}`,
              }))}
              size="small"
            />
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
              gap: 12,
              marginTop: 12,
              maxHeight: 300,
              overflowY: 'auto',
            }}>
              {filteredTemplates.map(template => (
                <Card
                  key={template.id}
                  hoverable
                  size="small"
                  onClick={() => handleTemplateSelect(template)}
                  style={{
                    cursor: 'pointer',
                    border: selectedTemplate?.id === template.id ? '2px solid #1890ff' : undefined,
                  }}
                >
                  <Space direction="vertical" style={{ width: '100%' }} size="small">
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontSize: 18 }}>{template.icon}</span>
                      {selectedTemplate?.id === template.id && (
                        <Tag color="blue">已选择</Tag>
                      )}
                    </div>
                    <div style={{ fontWeight: 500, fontSize: 14 }}>{template.name}</div>
                    <div style={{ color: '#999', fontSize: 12 }}>{template.description}</div>
                    {template.placeholders.length > 0 && (
                      <Tag color="orange" style={{ fontSize: 11 }}>
                        需填写 {template.placeholders.join('、')}
                      </Tag>
                    )}
                  </Space>
                </Card>
              ))}
            </div>
          </div>

          {/* Manual Input */}
          <div>
            <label style={{ display: 'block', marginBottom: 8, fontWeight: 500 }}>
              ✏️ 自定义输入
            </label>
            <Form
              form={form}
              layout="vertical"
              initialValues={{
                task_type: 'instruction',
              }}
              style={{ marginTop: 8 }}
            >
              <Form.Item
                label="任务类型"
                name="task_type"
                rules={[{ required: true, message: '请选择任务类型' }]}
                style={{ marginBottom: 12 }}
              >
                <Select>
                  <Option value="instruction">🔧 指令 - 执行某个操作（如创建日程、写文件等）</Option>
                  <Option value="rule">📜 规则 - 保存一条规则到记忆中</Option>
                  <Option value="conversation">💬 对话 - 普通对话（不创建任务）</Option>
                </Select>
              </Form.Item>

              <Form.Item
                label="查询内容"
                name="query"
                rules={[{ required: true, message: '请输入查询内容' }]}
                style={{ marginBottom: 0 }}
              >
                <TextArea
                  rows={3}
                  placeholder="例如：创建一个每天早上 9 点运行的日程，内容是'晨会'"
                />
              </Form.Item>
            </Form>
          </div>
        </Space>
      </div>
    </Modal>
  );
};

export default CreateTaskModal;
