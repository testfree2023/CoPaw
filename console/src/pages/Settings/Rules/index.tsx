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
import styles from "./index.module.less";

const { TextArea } = Input;
const { Option } = Select;

interface Rule {
  id: string;
  content: string;
  scope: string;
  priority: number;
  channel?: string;
  user_id?: string;
  session_id?: string;
  description?: string;
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

const scopeColors: Record<string, string> = {
  GLOBAL: "blue",
  CHANNEL: "green",
  USER: "orange",
  SESSION: "purple",
};

function RulesPage() {
  const { t } = useTranslation();
  const [rules, setRules] = useState<Rule[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [editingRule, setEditingRule] = useState<Rule | null>(null);
  const [form] = Form.useForm();

  const fetchRules = useCallback(async () => {
    setLoading(true);
    try {
      const response = await fetch("/api/rules");
      const data = await response.json();
      setRules(data.rules || []);
    } catch (error) {
      message.error(t("rules.fetchError", "Failed to fetch rules"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    fetchRules();
  }, [fetchRules]);

  const handleAdd = () => {
    setEditingRule(null);
    form.resetFields();
    form.setFieldsValue({ scope: "GLOBAL", priority: 0, enabled: true });
    setModalVisible(true);
  };

  const handleEdit = (rule: Rule) => {
    setEditingRule(rule);
    form.setFieldsValue(rule);
    setModalVisible(true);
  };

  const handleDelete = async (ruleId: string) => {
    try {
      const response = await fetch(`/api/rules/${ruleId}`, {
        method: "DELETE",
      });
      if (response.ok) {
        message.success(t("rules.deleteSuccess", "Rule deleted"));
        fetchRules();
      } else {
        message.error(t("rules.deleteError", "Failed to delete rule"));
      }
    } catch (error) {
      message.error(t("rules.deleteError", "Failed to delete rule"));
    }
  };

  const handleToggle = async (ruleId: string) => {
    try {
      const response = await fetch(`/api/rules/${ruleId}/toggle`, {
        method: "POST",
      });
      if (response.ok) {
        message.success(t("rules.toggleSuccess", "Rule toggled"));
        fetchRules();
      } else {
        message.error(t("rules.toggleError", "Failed to toggle rule"));
      }
    } catch (error) {
      message.error(t("rules.toggleError", "Failed to toggle rule"));
    }
  };

  const handleSubmit = async (values: any) => {
    try {
      const url = editingRule
        ? `/api/rules/${editingRule.id}`
        : "/api/rules";
      const method = editingRule ? "PUT" : "POST";

      const response = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(values),
      });

      if (response.ok) {
        message.success(
          editingRule
            ? t("rules.updateSuccess", "Rule updated")
            : t("rules.createSuccess", "Rule created")
        );
        setModalVisible(false);
        fetchRules();
      } else {
        const error = await response.json();
        message.error(error.detail || t("rules.saveError", "Failed to save rule"));
      }
    } catch (error) {
      message.error(t("rules.saveError", "Failed to save rule"));
    }
  };

  const columns = [
    {
      title: t("rules.content", "Content"),
      dataIndex: "content",
      key: "content",
      ellipsis: true,
      width: 300,
    },
    {
      title: t("rules.scope", "Scope"),
      dataIndex: "scope",
      key: "scope",
      width: 100,
      render: (scope: string) => (
        <Tag color={scopeColors[scope] || "default"}>{scope}</Tag>
      ),
    },
    {
      title: t("rules.priority", "Priority"),
      dataIndex: "priority",
      key: "priority",
      width: 80,
      sorter: (a: Rule, b: Rule) => a.priority - b.priority,
    },
    {
      title: t("rules.channel", "Channel"),
      dataIndex: "channel",
      key: "channel",
      width: 100,
      render: (channel: string) => channel || "-",
    },
    {
      title: t("rules.status", "Status"),
      dataIndex: "enabled",
      key: "enabled",
      width: 80,
      render: (enabled: boolean, record: Rule) => (
        <Switch
          checked={enabled}
          onChange={() => handleToggle(record.id)}
          size="small"
        />
      ),
    },
    {
      title: t("rules.actions", "Actions"),
      key: "actions",
      width: 100,
      render: (_: any, record: Rule) => (
        <Space size="small">
          <Button
            type="text"
            icon={<EditOutlined />}
            onClick={() => handleEdit(record)}
          />
          <Popconfirm
            title={t("rules.deleteConfirm", "Are you sure to delete this rule?")}
            onConfirm={() => handleDelete(record.id)}
            okText={t("common.confirm", "Yes")}
            cancelText={t("common.cancel", "Cancel")}
          >
            <Button type="text" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <h1>{t("rules.title", "Rules Management")}</h1>
        <Button type="primary" icon={<PlusOutlined />} onClick={handleAdd}>
          {t("rules.add", "Add Rule")}
        </Button>
      </div>

      <div className={styles.content}>
        <Table
          columns={columns}
          dataSource={rules}
          rowKey="id"
          loading={loading}
          pagination={{ pageSize: 10 }}
        />
      </div>

      <Modal
        title={editingRule ? t("rules.edit", "Edit Rule") : t("rules.add", "Add Rule")}
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
            name="content"
            label={t("rules.content", "Content")}
            rules={[{ required: true, message: t("rules.contentRequired", "Please input rule content") }]}
          >
            <TextArea rows={3} placeholder={t("rules.contentPlaceholder", "Enter rule content")} />
          </Form.Item>

          <Form.Item
            name="scope"
            label={t("rules.scope", "Scope")}
            rules={[{ required: true }]}
          >
            <Select>
              <Option value="GLOBAL">{t("rules.scopeGlobal", "Global")}</Option>
              <Option value="CHANNEL">{t("rules.scopeChannel", "Channel")}</Option>
              <Option value="USER">{t("rules.scopeUser", "User")}</Option>
              <Option value="SESSION">{t("rules.scopeSession", "Session")}</Option>
            </Select>
          </Form.Item>

          <Form.Item
            name="priority"
            label={t("rules.priority", "Priority")}
          >
            <Input type="number" />
          </Form.Item>

          <Form.Item
            noStyle
            shouldUpdate={(prevValues, currentValues) => prevValues.scope !== currentValues.scope}
          >
            {({ getFieldValue }) => {
              const scope = getFieldValue("scope");
              return (
                <>
                  {scope === "CHANNEL" && (
                    <Form.Item
                      name="channel"
                      label={t("rules.channel", "Channel")}
                    >
                      <Input placeholder="dingtalk, feishu, etc." />
                    </Form.Item>
                  )}
                  {(scope === "USER" || scope === "SESSION") && (
                    <Form.Item
                      name="user_id"
                      label={t("rules.userId", "User ID")}
                    >
                      <Input placeholder="User identifier" />
                    </Form.Item>
                  )}
                  {scope === "SESSION" && (
                    <Form.Item
                      name="session_id"
                      label={t("rules.sessionId", "Session ID")}
                    >
                      <Input placeholder="Session identifier" />
                    </Form.Item>
                  )}
                </>
              );
            }}
          </Form.Item>

          <Form.Item
            name="description"
            label={t("rules.description", "Description")}
          >
            <Input placeholder={t("rules.descriptionPlaceholder", "Optional description")} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}

export default RulesPage;