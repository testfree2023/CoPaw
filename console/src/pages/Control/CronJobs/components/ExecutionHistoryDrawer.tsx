import { useState, useEffect } from "react";
import {
  Drawer,
  Button,
  Table,
  Tag,
} from "@agentscope-ai/design";
import { Typography } from "antd";
import type { CronJobSpecOutput, CronExecutionRecord } from "../../../../api/types";
import api from "../../../../api";
import styles from "./ExecutionHistoryDrawer.module.less";

interface ExecutionHistoryDrawerProps {
  open: boolean;
  job: CronJobSpecOutput | null;
  onClose: () => void;
}

const { Text } = Typography;

const statusColorMap: Record<string, string> = {
  pending: "default",
  running: "processing",
  success: "success",
  error: "error",
  timeout: "warning",
};

const triggerSourceLabel: Record<string, string> = {
  schedule: "定时",
  manual: "手动",
};

export function ExecutionHistoryDrawer({
  open,
  job,
  onClose,
}: ExecutionHistoryDrawerProps) {
  const [history, setHistory] = useState<CronExecutionRecord[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchHistory = async () => {
    if (!job?.id) return;
    setLoading(true);
    try {
      const data = await api.getCronJobHistory(job.id, 50);
      setHistory(data || []);
    } catch (error) {
      console.error("Failed to load execution history", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (open && job?.id) {
      fetchHistory();
    }
  }, [open, job?.id]);

  const formatDateTime = (isoString?: string | null) => {
    if (!isoString) return "-";
    try {
      const date = new Date(isoString);
      return date.toLocaleString("zh-CN", {
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      });
    } catch {
      return isoString;
    }
  };

  const formatDuration = (ms?: number | null) => {
    if (ms === undefined || ms === null) return "-";
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(1)}s`;
  };

  const columns = [
    {
      title: "状态",
      dataIndex: "status",
      key: "status",
      width: 100,
      render: (status: string) => (
        <Tag color={statusColorMap[status] || "default"}>
          {status.toUpperCase()}
        </Tag>
      ),
    },
    {
      title: "触发方式",
      dataIndex: "trigger_source",
      key: "trigger_source",
      width: 80,
      render: (source: string) => triggerSourceLabel[source] || source,
    },
    {
      title: "触发时间",
      dataIndex: "triggered_at",
      key: "triggered_at",
      width: 180,
      render: formatDateTime,
    },
    {
      title: "开始时间",
      dataIndex: "started_at",
      key: "started_at",
      width: 180,
      render: formatDateTime,
    },
    {
      title: "完成时间",
      dataIndex: "completed_at",
      key: "completed_at",
      width: 180,
      render: formatDateTime,
    },
    {
      title: "耗时",
      dataIndex: "duration_ms",
      key: "duration_ms",
      width: 80,
      render: formatDuration,
    },
    {
      title: "错误信息",
      dataIndex: "error_message",
      key: "error_message",
      width: 200,
      ellipsis: true,
      render: (msg?: string | null) => (
        <Text type="danger" style={{ fontSize: 12 }}>
          {msg || "-"}
        </Text>
      ),
    },
  ];

  return (
    <Drawer
      title={`执行历史 - ${job?.name || ""}`}
      placement="right"
      width={1000}
      open={open}
      onClose={onClose}
      footer={
        <div style={{ display: "flex", justifyContent: "flex-end" }}>
          <Button onClick={onClose}>关闭</Button>
        </div>
      }
    >
      <div className={styles.historyContainer}>
        <Table
          columns={columns}
          dataSource={history}
          loading={loading}
          rowKey="id"
          pagination={{
            pageSize: 20,
            showSizeChanger: false,
            showTotal: (total) => `共 ${total} 条记录`,
          }}
          scroll={{ y: 600 }}
        />
      </div>
    </Drawer>
  );
}
