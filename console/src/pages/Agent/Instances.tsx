import { useState, useCallback, useEffect } from "react";
import {
  Button,
  Modal,
  message,
  Table,
  Tag,
  Space,
  Switch,
  Input,
  Select,
  Form,
  Popconfirm,
} from "antd";
import { PlusOutlined, EditOutlined, DeleteOutlined } from "@ant-design/icons";
import { useTranslation } from "react-i18next";
import styles from "./Instances.module.less";

const { TextArea } = Input;
const { Option } = Select;

interface AgentInstance {
  id: string;
  name: string;
  description?: string;
  agent_type: string;
  system_prompt: string;
  scope: string;
  channel?: string;
  user_ids?: string;  // Space-separated user IDs
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

const scopeColors: Record<string, string> = {
  global: "blue",
  channel: "green",
  user: "orange",
  user_channel: "purple",
};

const agentTypeOptions: Record<string, string> = {
  custom: "自定义",
  teacher: "教师",
  expert: "技术专家",
  investor: "投资顾问",
  assistant: "助手",
};

function AgentInstancesPage() {
  const { t } = useTranslation();
  const [instances, setInstances] = useState<AgentInstance[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [editingInstance, setEditingInstance] = useState<AgentInstance | null>(null);
  const [form] = Form.useForm();

  const fetchInstances = useCallback(async () => {
    setLoading(true);
    try {
      const response = await fetch("/api/agent-instances");
      const data = await response.json();
      setInstances(data.instances || []);
    } catch (error) {
      message.error(t("agentInstances.fetchError", "Failed to fetch agent instances"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    fetchInstances();
  }, [fetchInstances]);

  const handleAdd = () => {
    setEditingInstance(null);
    form.resetFields();
    form.setFieldsValue({ scope: "global", enabled: true, agent_type: "custom" });
    setModalVisible(true);
  };

  const handleEdit = (instance: AgentInstance) => {
    setEditingInstance(instance);
    form.setFieldsValue(instance);
    setModalVisible(true);
  };

  const handleDelete = async (instanceId: string) => {
    try {
      const response = await fetch(`/api/agent-instances/${instanceId}`, {
        method: "DELETE",
      });
      if (response.ok) {
        message.success(t("agentInstances.deleteSuccess", "Agent instance deleted"));
        fetchInstances();
      } else {
        message.error(t("agentInstances.deleteError", "Failed to delete agent instance"));
      }
    } catch (error) {
      message.error(t("agentInstances.deleteError", "Failed to delete agent instance"));
    }
  };

  const handleToggle = async (instanceId: string) => {
    try {
      const response = await fetch(`/api/agent-instances/${instanceId}/toggle`, {
        method: "POST",
      });
      if (response.ok) {
        message.success(t("agentInstances.toggleSuccess", "Agent instance toggled"));
        fetchInstances();
      } else {
        message.error(t("agentInstances.toggleError", "Failed to toggle agent instance"));
      }
    } catch (error) {
      message.error(t("agentInstances.toggleError", "Failed to toggle agent instance"));
    }
  };

  const handleSubmit = async (values: any) => {
    try {
      const url = editingInstance
        ? `/api/agent-instances/${editingInstance.id}`
        : "/api/agent-instances";
      const method = editingInstance ? "PUT" : "POST";

      const response = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(values),
      });

      if (response.ok) {
        message.success(
          editingInstance
            ? t("agentInstances.updateSuccess", "Agent instance updated")
            : t("agentInstances.createSuccess", "Agent instance created")
        );
        setModalVisible(false);
        fetchInstances();
      } else {
        const error = await response.json();
        message.error(error.detail || t("agentInstances.saveError", "Failed to save agent instance"));
      }
    } catch (error) {
      message.error(t("agentInstances.saveError", "Failed to save agent instance"));
    }
  };

  const columns = [
    {
      title: t("agentInstances.name", "Name"),
      dataIndex: "name",
      key: "name",
      width: 120,
      fixed: 'left' as const,
    },
    {
      title: t("agentInstances.description", "Description"),
      dataIndex: "description",
      key: "description",
      ellipsis: true,
      width: 200,
    },
    {
      title: t("agentInstances.agentType", "Agent Type"),
      dataIndex: "agent_type",
      key: "agent_type",
      width: 100,
      render: (type: string) => agentTypeOptions[type] || type,
    },
    {
      title: t("agentInstances.scope", "Scope"),
      dataIndex: "scope",
      key: "scope",
      width: 90,
      render: (scope: string) => (
        <Tag color={scopeColors[scope] || "default"}>{scope}</Tag>
      ),
    },
    {
      title: t("agentInstances.channel", "Channel"),
      dataIndex: "channel",
      key: "channel",
      width: 100,
      render: (channel: string) => channel || "-",
    },
    {
      title: t("agentInstances.userIds", "User IDs"),
      dataIndex: "user_ids",
      key: "user_ids",
      width: 150,
      render: (userIds: string) => userIds || "-",
    },
    {
      title: t("agentInstances.status", "Status"),
      dataIndex: "enabled",
      key: "enabled",
      width: 80,
      render: (enabled: boolean, record: AgentInstance) => (
        <Switch
          checked={enabled}
          onChange={() => handleToggle(record.id)}
          size="small"
        />
      ),
    },
    {
      title: t("agentInstances.actions", "Actions"),
      key: "actions",
      width: 120,
      fixed: 'right' as const,
      render: (_: any, record: AgentInstance) => (
        <Space size="small">
          <Button
            type="text"
            icon={<EditOutlined />}
            onClick={() => handleEdit(record)}
            title={t("agentInstances.edit", "Edit")}
          />
          <Popconfirm
            title={t("agentInstances.deleteConfirm", "Are you sure to delete this agent instance?")}
            onConfirm={() => handleDelete(record.id)}
            okText={t("common.confirm", "Yes")}
            cancelText={t("common.cancel", "Cancel")}
          >
            <Button type="text" danger icon={<DeleteOutlined />} title={t("common.delete", "Delete")} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <h1>{t("agentInstances.title", "Agent Instances Management")}</h1>
        <Button type="primary" icon={<PlusOutlined />} onClick={handleAdd}>
          {t("agentInstances.add", "Add Agent Instance")}
        </Button>
      </div>

      <div className={styles.content}>
        <Table
          columns={columns}
          dataSource={instances}
          rowKey="id"
          loading={loading}
          pagination={{ pageSize: 10 }}
          scroll={{ x: 1200 }}
        />
      </div>

      <Modal
        title={editingInstance ? t("agentInstances.edit", "Edit Agent Instance") : t("agentInstances.add", "Add Agent Instance")}
        open={modalVisible}
        onCancel={() => setModalVisible(false)}
        onOk={() => form.submit()}
        width={600}
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={handleSubmit}
        >
          <Form.Item
            name="name"
            label={t("agentInstances.name", "Name")}
            rules={[{ required: true, message: t("agentInstances.nameRequired", "Please input agent instance name") }]}
          >
            <Input placeholder={t("agentInstances.namePlaceholder", "e.g., Customer Service Assistant")} />
          </Form.Item>

          <Form.Item
            name="description"
            label={t("agentInstances.description", "Description")}
          >
            <Input placeholder={t("agentInstances.descriptionPlaceholder", "Brief description of this agent instance")} />
          </Form.Item>

          <Form.Item
            name="agent_type"
            label={t("agentInstances.agentType", "Agent Type")}
            rules={[{ required: true, message: t("agentInstances.agentTypeRequired", "Please select agent type") }]}
          >
            <Select>
              <Option value="custom">{agentTypeOptions.custom}</Option>
              <Option value="teacher">{agentTypeOptions.teacher}</Option>
              <Option value="expert">{agentTypeOptions.expert}</Option>
              <Option value="investor">{agentTypeOptions.investor}</Option>
              <Option value="assistant">{agentTypeOptions.assistant}</Option>
            </Select>
          </Form.Item>

          <Form.Item
            name="system_prompt"
            label={t("agentInstances.systemPrompt", "System Prompt")}
            rules={[{ required: true, message: t("agentInstances.systemPromptRequired", "Please input system prompt") }]}
          >
            <TextArea rows={4} placeholder={t("agentInstances.systemPromptPlaceholder", "Enter complete system prompt content")} />
          </Form.Item>

          <Form.Item
            name="scope"
            label={t("agentInstances.scope", "Scope")}
            rules={[{ required: true }]}
          >
            <Select>
              <Option value="global">{t("agentInstances.scopeGlobal", "Global")}</Option>
              <Option value="channel">{t("agentInstances.scopeChannel", "Channel")}</Option>
              <Option value="user">{t("agentInstances.scopeUser", "User")}</Option>
              <Option value="user_channel">{t("agentInstances.scopeUserChannel", "User + Channel")}</Option>
            </Select>
          </Form.Item>

          <Form.Item
            noStyle
            shouldUpdate={(prevValues, currentValues) => prevValues.scope !== currentValues.scope}
          >
            {({ getFieldValue }) => {
              const scope = getFieldValue("scope");
              return (
                <>
                  {(scope === "channel" || scope === "user_channel") && (
                    <Form.Item
                      name="channel"
                      label={t("agentInstances.channel", "Channel")}
                      rules={scope === "channel" || scope === "user_channel" ? [{ required: true, message: t("agentInstances.channelRequired", "Please input channel") }] : undefined}
                    >
                      <Input placeholder="dingtalk, feishu, etc." />
                    </Form.Item>
                  )}
                  {(scope === "user" || scope === "user_channel") && (
                    <Form.Item
                      name="user_ids"
                      label={t("agentInstances.userIds", "User IDs")}
                      rules={scope === "user" || scope === "user_channel" ? [{ required: true, message: t("agentInstances.userIdsRequired", "Please input user IDs") }] : undefined}
                    >
                      <Input placeholder="user1 user2 user3 (space-separated)" />
                    </Form.Item>
                  )}
                </>
              );
            }}
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}

export default AgentInstancesPage;
