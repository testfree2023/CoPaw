import { useState, useEffect } from "react";
import { Table, Tag, Card, Statistic, Row, Col, Typography, Space, Tabs, Badge } from "antd";
import { ShieldOutlined, AlertOutlined, CheckCircleOutlined, FileTextOutlined } from "@ant-design/icons";
import { useTranslation } from "react-i18next";
import styles from "./index.module.less";

const { Title, Text } = Typography;

interface SecurityRule {
  id: string;
  name: string;
  description: string;
  category: string;
  severity: string;
  scope: string;
  enabled: boolean;
  patterns: string[];
  created_at: string;
  updated_at: string;
}

interface SecurityState {
  total_rules: number;
  enabled_rules: number;
  violations_today: number;
  violations_total: number;
  last_violation_at: string | null;
}

interface Violation {
  id: string;
  rule_id: string;
  rule_name: string;
  input_content: string;
  matched_pattern: string;
  agent_type?: string;
  channel?: string;
  user_id?: string;
  triggered_at: string;
  action_taken: string;
}

const categoryColors: Record<string, string> = {
  content_safety: "red",
  data_privacy: "orange",
  system_security: "purple",
  ethical_guidelines: "blue",
  compliance: "green",
  custom: "gray",
};

const severityColors: Record<string, string> = {
  critical: "red",
  high: "orange",
  medium: "gold",
  low: "blue",
};

const scopeLabels: Record<string, string> = {
  global: "Global",
  agent: "Agent",
  channel: "Channel",
  user: "User",
};

function SecurityPage() {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(false);
  const [rules, setRules] = useState<SecurityRule[]>([]);
  const [state, setState] = useState<SecurityState | null>(null);
  const [violations, setViolations] = useState<Violation[]>([]);

  const fetchSecurityData = async () => {
    setLoading(true);
    try {
      const [rulesRes, stateRes, violationsRes] = await Promise.all([
        fetch("/api/security?enabled_only=false"),
        fetch("/api/security/state"),
        fetch("/api/security/violations/list?limit=50"),
      ]);

      if (rulesRes.ok) {
        const rulesData = await rulesRes.json();
        setRules(rulesData.rules || []);
      }

      if (stateRes.ok) {
        const stateData = await stateRes.json();
        setState(stateData.state || null);
      }

      if (violationsRes.ok) {
        const violationsData = await violationsRes.json();
        setViolations(violationsData.violations || []);
      }
    } catch (error) {
      console.error("Failed to fetch security data:", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSecurityData();
  }, []);

  const rulesColumns = [
    {
      title: t("security.ruleName"),
      dataIndex: "name",
      key: "name",
      width: 200,
      render: (name: string, record: SecurityRule) => (
        <Space direction="vertical" size={0}>
          <Text strong>{name}</Text>
          <Text type="secondary" style={{ fontSize: 12 }}>{record.description}</Text>
        </Space>
      ),
    },
    {
      title: t("security.category"),
      dataIndex: "category",
      key: "category",
      width: 120,
      render: (category: string) => (
        <Tag color={categoryColors[category] || "default"}>
          {category}
        </Tag>
      ),
    },
    {
      title: t("security.severity"),
      dataIndex: "severity",
      key: "severity",
      width: 100,
      render: (severity: string) => (
        <Tag color={severityColors[severity] || "default"}>
          {severity}
        </Tag>
      ),
    },
    {
      title: t("security.scope"),
      dataIndex: "scope",
      key: "scope",
      width: 80,
      render: (scope: string) => scopeLabels[scope] || scope,
    },
    {
      title: t("security.status"),
      dataIndex: "enabled",
      key: "enabled",
      width: 70,
      render: (enabled: boolean) => (
        enabled ? (
          <Badge status="success" text={t("security.enabled")} />
        ) : (
          <Badge status="default" text={t("security.disabled")} />
        )
      ),
    },
    {
      title: t("security.patterns"),
      dataIndex: "patterns",
      key: "patterns",
      ellipsis: true,
      render: (patterns: string[]) => (
        <Text type="secondary">{patterns?.slice(0, 3).join(", ")}{patterns?.length > 3 ? "..." : ""}</Text>
      ),
    },
  ];

  const violationsColumns = [
    {
      title: t("security.triggeredAt"),
      dataIndex: "triggered_at",
      key: "triggered_at",
      width: 160,
      render: (time: string) => new Date(time).toLocaleString(),
    },
    {
      title: t("security.triggeredRule"),
      dataIndex: "rule_name",
      key: "rule_name",
      width: 150,
      render: (name: string) => <Text strong>{name}</Text>,
    },
    {
      title: t("security.matchedPattern"),
      dataIndex: "matched_pattern",
      key: "matched_pattern",
      width: 120,
      render: (pattern: string) => (
        <Tag color="red">{pattern}</Tag>
      ),
    },
    {
      title: t("security.inputContent"),
      dataIndex: "input_content",
      key: "input_content",
      ellipsis: true,
      render: (content: string) => (
        <Text type="secondary" style={{ maxWidth: 300, display: "block", overflow: "hidden", textOverflow: "ellipsis" }}>
          {content?.slice(0, 50)}{content?.length > 50 ? "..." : ""}
        </Text>
      ),
    },
    {
      title: t("security.channel"),
      dataIndex: "channel",
      key: "channel",
      width: 100,
      render: (channel?: string) => channel || "-",
    },
    {
      title: t("security.user"),
      dataIndex: "user_id",
      key: "user_id",
      width: 150,
      render: (userId?: string) => userId ? `${userId.slice(0, 10)}...` : "-",
    },
    {
      title: t("security.action"),
      dataIndex: "action_taken",
      key: "action_taken",
      width: 80,
      render: (action: string) => (
        <Tag color="red">{action === "blocked" ? t("security.blocked") : action}</Tag>
      ),
    },
  ];

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <Title level={3}>
          <ShieldOutlined style={{ marginRight: 8 }} />
          {t("security.title")}
        </Title>
        <Text type="secondary">{t("security.subtitle")}</Text>
      </div>

      {/* Status Overview */}
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={6}>
          <Card>
            <Statistic
              title={t("security.totalRules")}
              value={state?.total_rules || 0}
              prefix={<FileTextOutlined />}
              valueStyle={{ color: "#1890ff" }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title={t("security.enabledRules")}
              value={state?.enabled_rules || 0}
              prefix={<CheckCircleOutlined />}
              valueStyle={{ color: "#52c41a" }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title={t("security.violationsToday")}
              value={state?.violations_today || 0}
              prefix={<AlertOutlined />}
              valueStyle={{ color: state?.violations_today ? "#faad14" : "#52c41a" }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title={t("security.violationsTotal")}
              value={state?.violations_total || 0}
              prefix={<ShieldOutlined />}
            />
          </Card>
        </Col>
      </Row>

      {/* Rules and Violations Tabs */}
      <Tabs
        items={[
          {
            key: "rules",
            label: `${t("security.rulesTab")} (${rules.length})`,
            children: (
              <Table
                columns={rulesColumns}
                dataSource={rules}
                rowKey="id"
                loading={loading}
                pagination={{ pageSize: 10 }}
              />
            ),
          },
          {
            key: "violations",
            label: `${t("security.violationsTab")} (${violations.length})`,
            children: (
              <Table
                columns={violationsColumns}
                dataSource={violations}
                rowKey="id"
                loading={loading}
                pagination={{ pageSize: 10 }}
              />
            ),
          },
        ]}
      />
    </div>
  );
}

export default SecurityPage;
