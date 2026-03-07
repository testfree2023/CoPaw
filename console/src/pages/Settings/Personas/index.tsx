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

interface Persona {
  id: string;
  name: string;
  description?: string;
  system_prompt_addon: string;
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

function PersonasPage() {
  const { t } = useTranslation();
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [editingPersona, setEditingPersona] = useState<Persona | null>(null);
  const [form] = Form.useForm();

  const fetchPersonas = useCallback(async () => {
    setLoading(true);
    try {
      const response = await fetch("/api/personas");
      const data = await response.json();
      setPersonas(data.personas || []);
    } catch (error) {
      message.error(t("personas.fetchError", "Failed to fetch personas"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    fetchPersonas();
  }, [fetchPersonas]);

  const handleAdd = () => {
    setEditingPersona(null);
    form.resetFields();
    form.setFieldsValue({ scope: "global", enabled: true });
    setModalVisible(true);
  };

  const handleEdit = (persona: Persona) => {
    setEditingPersona(persona);
    form.setFieldsValue(persona);
    setModalVisible(true);
  };

  const handleDelete = async (personaId: string) => {
    try {
      const response = await fetch(`/api/personas/${personaId}`, {
        method: "DELETE",
      });
      if (response.ok) {
        message.success(t("personas.deleteSuccess", "Persona deleted"));
        fetchPersonas();
      } else {
        message.error(t("personas.deleteError", "Failed to delete persona"));
      }
    } catch (error) {
      message.error(t("personas.deleteError", "Failed to delete persona"));
    }
  };

  const handleToggle = async (personaId: string) => {
    try {
      const response = await fetch(`/api/personas/${personaId}/toggle`, {
        method: "POST",
      });
      if (response.ok) {
        message.success(t("personas.toggleSuccess", "Persona toggled"));
        fetchPersonas();
      } else {
        message.error(t("personas.toggleError", "Failed to toggle persona"));
      }
    } catch (error) {
      message.error(t("personas.toggleError", "Failed to toggle persona"));
    }
  };

  const handleSubmit = async (values: any) => {
    try {
      const url = editingPersona
        ? `/api/personas/${editingPersona.id}`
        : "/api/personas";
      const method = editingPersona ? "PUT" : "POST";

      const response = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(values),
      });

      if (response.ok) {
        message.success(
          editingPersona
            ? t("personas.updateSuccess", "Persona updated")
            : t("personas.createSuccess", "Persona created")
        );
        setModalVisible(false);
        fetchPersonas();
      } else {
        const error = await response.json();
        message.error(error.detail || t("personas.saveError", "Failed to save persona"));
      }
    } catch (error) {
      message.error(t("personas.saveError", "Failed to save persona"));
    }
  };

  const columns = [
    {
      title: t("personas.name", "Name"),
      dataIndex: "name",
      key: "name",
      width: 150,
    },
    {
      title: t("personas.description", "Description"),
      dataIndex: "description",
      key: "description",
      ellipsis: true,
      width: 200,
    },
    {
      title: t("personas.scope", "Scope"),
      dataIndex: "scope",
      key: "scope",
      width: 120,
      render: (scope: string) => (
        <Tag color={scopeColors[scope] || "default"}>{scope}</Tag>
      ),
    },
    {
      title: t("personas.channel", "Channel"),
      dataIndex: "channel",
      key: "channel",
      width: 100,
      render: (channel: string) => channel || "-",
    },
    {
      title: t("personas.user", "User"),
      dataIndex: "user_ids",
      key: "user_ids",
      width: 150,
      render: (userIds: string) => userIds || "-",
    },
    {
      title: t("personas.status", "Status"),
      dataIndex: "enabled",
      key: "enabled",
      width: 80,
      render: (enabled: boolean, record: Persona) => (
        <Switch
          checked={enabled}
          onChange={() => handleToggle(record.id)}
          size="small"
        />
      ),
    },
    {
      title: t("personas.actions", "Actions"),
      key: "actions",
      width: 100,
      render: (_: any, record: Persona) => (
        <Space size="small">
          <Button
            type="text"
            icon={<EditOutlined />}
            onClick={() => handleEdit(record)}
          />
          <Popconfirm
            title={t("personas.deleteConfirm", "Are you sure to delete this persona?")}
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
        <h1>{t("personas.title", "Personas Management")}</h1>
        <Button type="primary" icon={<PlusOutlined />} onClick={handleAdd}>
          {t("personas.add", "Add Persona")}
        </Button>
      </div>

      <div className={styles.content}>
        <Table
          columns={columns}
          dataSource={personas}
          rowKey="id"
          loading={loading}
          pagination={{ pageSize: 10 }}
          scroll={{ x: 1000 }}
        />
      </div>

      <Modal
        title={editingPersona ? t("personas.edit", "Edit Persona") : t("personas.add", "Add Persona")}
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
            label={t("personas.name", "Name")}
            rules={[{ required: true, message: t("personas.nameRequired", "Please input persona name") }]}
          >
            <Input placeholder={t("personas.namePlaceholder", "e.g., Customer Service Assistant")} />
          </Form.Item>

          <Form.Item
            name="description"
            label={t("personas.description", "Description")}
          >
            <Input placeholder={t("personas.descriptionPlaceholder", "Brief description of this persona")} />
          </Form.Item>

          <Form.Item
            name="system_prompt_addon"
            label={t("personas.systemPrompt", "System Prompt Add-on")}
            rules={[{ required: true, message: t("personas.systemPromptRequired", "Please input system prompt") }]}
          >
            <TextArea rows={4} placeholder={t("personas.systemPromptPlaceholder", "Enter additional system prompt content")} />
          </Form.Item>

          <Form.Item
            name="scope"
            label={t("personas.scope", "Scope")}
            rules={[{ required: true }]}
          >
            <Select>
              <Option value="global">{t("personas.scopeGlobal", "Global")}</Option>
              <Option value="channel">{t("personas.scopeChannel", "Channel")}</Option>
              <Option value="user">{t("personas.scopeUser", "User")}</Option>
              <Option value="user_channel">{t("personas.scopeUserChannel", "User + Channel")}</Option>
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
                      label={t("personas.channel", "Channel")}
                      rules={scope === "channel" || scope === "user_channel" ? [{ required: true, message: t("personas.channelRequired", "Please input channel") }] : undefined}
                    >
                      <Input placeholder="dingtalk, feishu, etc." />
                    </Form.Item>
                  )}
                  {(scope === "user" || scope === "user_channel") && (
                    <Form.Item
                      name="user_ids"
                      label={t("personas.userIds", "User IDs")}
                      rules={scope === "user" || scope === "user_channel" ? [{ required: true, message: t("personas.userIdsRequired", "Please input user IDs") }] : undefined}
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

export default PersonasPage;