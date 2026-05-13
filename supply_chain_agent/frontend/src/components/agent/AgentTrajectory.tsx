import { useState, useEffect, useRef, memo } from 'react';
import { Tag, Badge, Button, Modal, Typography, Empty } from 'antd';
import {
  CheckCircleOutlined,
  SyncOutlined,
  ClockCircleOutlined,
  CloseCircleOutlined,
  CodeOutlined,
  RightOutlined,
} from '@ant-design/icons';
import type { AgentTrajectory, AgentStep, ToolCall, AgentType } from '@/types/agent';
import { AGENT_TYPE_LABELS, AGENT_TYPE_COLORS } from '@/types/agent';

const { Text } = Typography;

interface AgentTrajectoryPanelProps {
  trajectory: AgentTrajectory | null;
}

// 获取步骤状态图标
const getStepIcon = (status: string) => {
  switch (status) {
    case 'success':
      return <CheckCircleOutlined style={{ color: '#52c41a', fontSize: 14 }} />;
    case 'error':
      return <CloseCircleOutlined style={{ color: '#ff4d4f', fontSize: 14 }} />;
    case 'running':
      return <SyncOutlined spin style={{ color: '#1890ff', fontSize: 14 }} />;
    default:
      return <ClockCircleOutlined style={{ color: '#d9d9d9', fontSize: 14 }} />;
  }
};

// 获取Agent类型标签
const getAgentTypeLabel = (type: AgentType): string => {
  return AGENT_TYPE_LABELS[type] || type;
};

// 获取Agent类型颜色
const getAgentTypeColor = (type: AgentType): string => {
  return AGENT_TYPE_COLORS[type] || 'default';
};

// 格式化持续时间
const formatDuration = (ms: number): string => {
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  const minutes = Math.floor(ms / 60000);
  const seconds = Math.floor((ms % 60000) / 1000);
  return `${minutes}m ${seconds}s`;
};

// 工具调用卡片组件
interface ToolCallItemProps {
  tool: ToolCall;
}

const ToolCallItem = memo(({ tool }: ToolCallItemProps) => {
  const duration = tool.endTime
    ? formatDuration(tool.endTime - tool.startTime)
    : '进行中...';

  return (
    <div
      style={{
        padding: '8px 12px',
        background: 'var(--bg-tertiary)',
        borderRadius: 6,
        marginBottom: 6,
        border: '1px solid var(--border-light)',
      }}
    >
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 4,
        }}
      >
        <Text strong style={{ fontSize: 12 }}>{tool.name}</Text>
        <Tag
          color={tool.status === 'success' ? 'success' : tool.status === 'error' ? 'error' : 'processing'}
          style={{ fontSize: 10, margin: 0 }}
        >
          {duration}
        </Tag>
      </div>
      {tool.response && (
        <pre
          style={{
            margin: 0,
            padding: 4,
            background: 'rgba(82, 196, 26, 0.1)',
            borderRadius: 4,
            fontSize: 10,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
            maxWidth: '100%',
          }}
        >
          {JSON.stringify(tool.response)}
        </pre>
      )}
    </div>
  );
});

ToolCallItem.displayName = 'ToolCallItem';

// 步骤卡片组件
interface StepItemProps {
  step: AgentStep;
  isLast?: boolean;
  isNew?: boolean;
}

const StepItem = memo(({ step, isLast, isNew }: StepItemProps) => {
  const [jsonModalVisible, setJsonModalVisible] = useState(false);
  const [toolsExpanded, setToolsExpanded] = useState(step.status === 'running');

  const duration = step.endTime
    ? formatDuration(step.endTime - step.startTime)
    : step.status === 'running'
      ? '进行中...'
      : '-';

  return (
    <div
      style={{
        position: 'relative',
        marginBottom: isLast ? 0 : 16,
      }}
    >
      {/* 连接线 */}
      {!isLast && (
        <div
          style={{
            position: 'absolute',
            left: 7,
            top: 24,
            width: 2,
            height: 'calc(100% - 8px)',
            background: 'var(--border-color)',
          }}
        />
      )}

      {/* 步骤内容 */}
      <div
        style={{
          display: 'flex',
          gap: 12,
        }}
        className={isNew ? 'step-highlight' : ''}
      >
        {/* 状态图标 */}
        <div
          style={{
            width: 16,
            height: 16,
            borderRadius: '50%',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0,
            background: 'var(--bg-primary)',
            zIndex: 1,
          }}
        >
          {getStepIcon(step.status)}
        </div>

        {/* 步骤详情 */}
        <div style={{ flex: 1, minWidth: 0 }}>
          {/* 标题行 */}
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: 4,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Text strong style={{ fontSize: 13 }}>{step.title}</Text>
              <Tag color={getAgentTypeColor(step.agentType)} style={{ fontSize: 10, margin: 0 }}>
                {getAgentTypeLabel(step.agentType)}
              </Tag>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <Text type="secondary" style={{ fontSize: 11 }}>{duration}</Text>
              <Button
                type="text"
                size="small"
                icon={<CodeOutlined style={{ fontSize: 12 }} />}
                onClick={() => setJsonModalVisible(true)}
                style={{ padding: '0 4px', height: 'auto' }}
              />
            </div>
          </div>

          {/* 描述 */}
          <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 8 }}>
            {step.description}
          </Text>

          {/* 工具调用列表 */}
          {step.tools.length > 0 && (
            <div style={{ marginTop: 8 }}>
              <div
                onClick={() => setToolsExpanded(!toolsExpanded)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 4,
                  cursor: 'pointer',
                  color: 'var(--text-secondary)',
                  fontSize: 12,
                  marginBottom: toolsExpanded ? 8 : 0,
                }}
              >
                <RightOutlined
                  style={{
                    fontSize: 10,
                    transform: toolsExpanded ? 'rotate(90deg)' : 'rotate(0deg)',
                    transition: 'transform 0.2s',
                  }}
                />
                <span>工具调用 ({step.tools.length})</span>
              </div>
              {toolsExpanded && (
                <div>
                  {step.tools.map((tool) => (
                    <ToolCallItem key={tool.id} tool={tool} />
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* JSON详情弹窗 */}
      <Modal
        title={`步骤详情: ${step.title}`}
        open={jsonModalVisible}
        onCancel={() => setJsonModalVisible(false)}
        footer={null}
        width={500}
      >
        <pre
          style={{
            padding: 12,
            background: 'var(--bg-secondary)',
            borderRadius: 8,
            fontSize: 11,
            overflow: 'auto',
            maxHeight: 400,
          }}
        >
          {JSON.stringify(step, null, 2)}
        </pre>
      </Modal>
    </div>
  );
});

StepItem.displayName = 'StepItem';

export const AgentTrajectoryPanel = memo(({ trajectory }: AgentTrajectoryPanelProps) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [prevStepsCount, setPrevStepsCount] = useState(0);

  // 自动滚动到底部
  useEffect(() => {
    if (trajectory && trajectory.steps.length > prevStepsCount) {
      if (containerRef.current) {
        containerRef.current.scrollTop = containerRef.current.scrollHeight;
      }
    }
    setPrevStepsCount(trajectory?.steps.length || 0);
  }, [trajectory?.steps.length, prevStepsCount]);

  // 空状态
  if (!trajectory || trajectory.steps.length === 0) {
    return (
      <div
        style={{
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          padding: 24,
          background: 'var(--bg-secondary)',
          color: 'var(--text-tertiary)',
        }}
      >
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description={
            <div style={{ textAlign: 'center' }}>
              <p style={{ margin: 0, fontSize: 13 }}>Agent执行轨迹</p>
              <p style={{ fontSize: 11, marginTop: 4 }}>发送消息后查看处理过程</p>
            </div>
          }
        />
      </div>
    );
  }

  const duration = trajectory.endTime
    ? trajectory.endTime - trajectory.startTime
    : Date.now() - trajectory.startTime;

  const statusConfig: Record<string, { status: 'success' | 'processing' | 'error' | 'default'; text: string }> = {
    running: { status: 'processing', text: '处理中' },
    success: { status: 'success', text: '已完成' },
    error: { status: 'error', text: '出错' },
    pending: { status: 'default', text: '等待中' },
    warning: { status: 'default', text: '警告' },
  };

  const statusInfo = statusConfig[trajectory.overallStatus] || statusConfig.pending;

  return (
    <div
      ref={containerRef}
      style={{
        padding: 16,
        height: '100%',
        overflowY: 'auto',
        background: 'var(--bg-secondary)',
      }}
    >
      {/* 头部状态栏 */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          paddingBottom: 12,
          borderBottom: '1px solid var(--border-light)',
          marginBottom: 16,
        }}
      >
        <Text strong style={{ fontSize: 13 }}>Agent执行轨迹</Text>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Badge status={statusInfo.status} text={statusInfo.text} />
          <Tag style={{ margin: 0, fontSize: 11 }}>{formatDuration(duration)}</Tag>
        </div>
      </div>

      {/* 步骤列表 */}
      <div>
        {trajectory.steps.map((step, index) => (
          <StepItem
            key={step.id}
            step={step}
            isLast={index === trajectory.steps.length - 1}
            isNew={index === trajectory.steps.length - 1 && step.status === 'running'}
          />
        ))}
      </div>
    </div>
  );
});

AgentTrajectoryPanel.displayName = 'AgentTrajectoryPanel';

export default AgentTrajectoryPanel;
