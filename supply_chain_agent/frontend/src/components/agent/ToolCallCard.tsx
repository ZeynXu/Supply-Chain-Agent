import { Card, Tag, Button, Modal, Typography } from 'antd';
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  SyncOutlined,
  CodeOutlined,
} from '@ant-design/icons';
import { useState, memo } from 'react';
import type { ToolCall } from '@/types/agent';

const { Text } = Typography;

interface ToolCallCardProps {
  tool: ToolCall;
  compact?: boolean;
}

const getStatusIcon = (status: string) => {
  switch (status) {
    case 'success':
      return <CheckCircleOutlined style={{ color: '#52c41a' }} />;
    case 'error':
      return <CloseCircleOutlined style={{ color: '#ff4d4f' }} />;
    case 'running':
      return <SyncOutlined spin style={{ color: '#1890ff' }} />;
    default:
      return null;
  }
};

const getStatusColor = (status: string): string => {
  switch (status) {
    case 'success':
      return 'success';
    case 'error':
      return 'error';
    case 'running':
      return 'processing';
    default:
      return 'default';
  }
};

const formatDuration = (start: number, end?: number): string => {
  if (!end) return '进行中...';
  const ms = end - start;
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
};

export const ToolCallCard = memo(({ tool, compact = false }: ToolCallCardProps) => {
  const [jsonModalVisible, setJsonModalVisible] = useState(false);

  const duration = formatDuration(tool.startTime, tool.endTime);

  if (compact) {
    return (
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        padding: '4px 8px',
        background: 'var(--bg-secondary)',
        borderRadius: 4,
        fontSize: 12,
      }}>
        {getStatusIcon(tool.status)}
        <span>{tool.name}</span>
        <Tag color={getStatusColor(tool.status)} style={{ margin: 0, fontSize: 10 }}>
          {duration}
        </Tag>
      </div>
    );
  }

  return (
    <>
      <Card
        size="small"
        style={{
          marginBottom: 8,
          borderRadius: 8,
          border: `1px solid var(--border-light)`,
        }}
        styles={{
          body: { padding: 12 },
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            {getStatusIcon(tool.status)}
            <Text strong style={{ fontSize: 13 }}>{tool.name}</Text>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Tag color={getStatusColor(tool.status)}>{duration}</Tag>
            <Button
              type="text"
              size="small"
              icon={<CodeOutlined />}
              onClick={() => setJsonModalVisible(true)}
            >
              详情
            </Button>
          </div>
        </div>

        {/* 参数显示 */}
        <div style={{ marginBottom: 8 }}>
          <Text type="secondary" style={{ fontSize: 11 }}>参数:</Text>
          <pre style={{
            margin: '4px 0 0 0',
            padding: 8,
            background: 'var(--bg-tertiary)',
            borderRadius: 4,
            fontSize: 11,
            overflow: 'auto',
            maxHeight: 80,
          }}>
            {JSON.stringify(tool.parameters, null, 2)}
          </pre>
        </div>

        {/* 结果显示 */}
        {tool.status === 'success' && tool.response && (
          <div>
            <Text type="secondary" style={{ fontSize: 11 }}>返回结果:</Text>
            <pre style={{
              margin: '4px 0 0 0',
              padding: 8,
              background: 'rgba(82, 196, 26, 0.1)',
              borderRadius: 4,
              fontSize: 11,
              overflow: 'auto',
              maxHeight: 120,
              border: '1px solid rgba(82, 196, 26, 0.2)',
            }}>
              {JSON.stringify(tool.response, null, 2)}
            </pre>
          </div>
        )}

        {/* 错误显示 */}
        {tool.status === 'error' && tool.error && (
          <div>
            <Text type="secondary" style={{ fontSize: 11, color: '#ff4d4f' }}>错误信息:</Text>
            <pre style={{
              margin: '4px 0 0 0',
              padding: 8,
              background: 'rgba(255, 77, 79, 0.1)',
              borderRadius: 4,
              fontSize: 11,
              color: '#ff4d4f',
              border: '1px solid rgba(255, 77, 79, 0.2)',
            }}>
              {tool.error}
            </pre>
          </div>
        )}
      </Card>

      {/* JSON详情弹窗 */}
      <Modal
        title={`工具调用详情: ${tool.name}`}
        open={jsonModalVisible}
        onCancel={() => setJsonModalVisible(false)}
        footer={null}
        width={600}
      >
        <div style={{ maxHeight: 500, overflow: 'auto' }}>
          <h4 style={{ marginBottom: 8 }}>完整数据</h4>
          <pre style={{
            padding: 12,
            background: 'var(--bg-secondary)',
            borderRadius: 8,
            fontSize: 12,
            overflow: 'auto',
          }}>
            {JSON.stringify(tool, null, 2)}
          </pre>
        </div>
      </Modal>
    </>
  );
});

ToolCallCard.displayName = 'ToolCallCard';

export default ToolCallCard;
