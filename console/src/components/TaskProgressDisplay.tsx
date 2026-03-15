import React from 'react';
import { Timeline, Tag, Alert } from 'antd';
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  SyncOutlined,
  ClockCircleOutlined,
  LoadingOutlined,
} from '@ant-design/icons';
import type { TaskProgressState } from '../hooks/useTaskProgress';

interface TaskProgressDisplayProps {
  taskId: string;
  progress: TaskProgressState;
}

export const TaskProgressDisplay: React.FC<TaskProgressDisplayProps> = ({
  progress,
}) => {
  const { status, events, error, verified, response } = progress;

  // Get status icon and color
  const getStatusInfo = () => {
    switch (status) {
      case 'completed':
        return {
          icon: <CheckCircleOutlined />,
          color: 'success',
          text: '已完成',
        };
      case 'failed':
        return {
          icon: <CloseCircleOutlined />,
          color: 'error',
          text: '失败',
        };
      case 'processing':
        return {
          icon: <LoadingOutlined spin />,
          color: 'processing',
          text: '处理中',
        };
      case 'pending':
        return {
          icon: <ClockCircleOutlined />,
          color: 'warning',
          text: '等待中',
        };
      case 'retrying':
        return {
          icon: <SyncOutlined spin />,
          color: 'warning',
          text: '重试中',
        };
      case 'waiting_verification':
        return {
          icon: <LoadingOutlined />,
          color: 'processing',
          text: '验证中',
        };
      default:
        return {
          icon: <ClockCircleOutlined />,
          color: 'default',
          text: status || '未知',
        };
    }
  };

  const statusInfo = getStatusInfo();

  // Format event display
  const getEventDisplay = (eventType: string) => {
    const eventLabels: Record<string, string> = {
      status: '状态更新',
      result: '处理结果',
      thought: '思考',
      tool: '工具调用',
      progress: '进度更新',
    };
    return eventLabels[eventType] || eventType;
  };

  // Get event color
  const getEventColor = (eventType: string) => {
    const colorMap: Record<string, string> = {
      status: 'blue',
      result: 'green',
      thought: 'purple',
      tool: 'orange',
      progress: 'cyan',
    };
    return colorMap[eventType] || 'gray';
  };

  // Check if we should show response from initial state (when no events but response exists)
  const showInitialResponse = response && events.length === 0 && status === 'completed';

  return (
    <div style={{ marginTop: 12, padding: '12px', background: '#fafafa', borderRadius: 8 }}>
      {/* Status Header */}
      <div style={{ marginBottom: 12 }}>
        <Tag icon={statusInfo.icon} color={statusInfo.color}>
          {statusInfo.text}
        </Tag>
        {verified !== undefined && (
          <Tag color={verified ? 'success' : 'error'}>
            {verified ? '已验证' : '未验证'}
          </Tag>
        )}
      </div>

      {/* Error Alert */}
      {error && (
        <Alert
          message="处理失败"
          description={error}
          type="error"
          showIcon
          style={{ marginBottom: 12 }}
        />
      )}

      {/* Show initial response if task completed before WebSocket connected */}
      {showInitialResponse && (
        <Alert
          message="处理完成"
          description={response}
          type="success"
          showIcon
          style={{ marginBottom: 12 }}
        />
      )}

      {/* Timeline of Events */}
      {events.length > 0 ? (
        <Timeline
          items={events.map((event, index) => ({
            key: index,
            color: getEventColor(event.type),
            dot: event.type === 'result' ? <CheckCircleOutlined /> : undefined,
            children: (
              <div>
                <div style={{ fontWeight: 500 }}>
                  {getEventDisplay(event.type)}
                  {event.type === 'status' && event.data.status && (
                    <Tag style={{ marginLeft: 8, fontSize: 12 }}>
                      {event.data.status}
                    </Tag>
                  )}
                </div>
                {event.data.response && (
                  <div style={{ marginTop: 4, color: '#666' }}>
                    {event.data.response.length > 200
                      ? event.data.response.slice(0, 200) + '...'
                      : event.data.response}
                  </div>
                )}
                {event.data.reason && (
                  <div style={{ marginTop: 4, color: '#999' }}>
                    原因：{event.data.reason}
                  </div>
                )}
                <div style={{ fontSize: 12, color: '#999', marginTop: 4 }}>
                  {new Date(event.timestamp).toLocaleTimeString()}
                </div>
              </div>
            ),
          }))}
        />
      ) : !showInitialResponse && (
        <div style={{ color: '#999', textAlign: 'center', padding: 20 }}>
          正在等待任务更新...
        </div>
      )}
    </div>
  );
};
