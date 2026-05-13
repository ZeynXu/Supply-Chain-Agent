import { Badge, Button, Space, Typography } from 'antd';
import { RobotOutlined, ClearOutlined } from '@ant-design/icons';
import { ChatMessage } from '@/components/chat/ChatMessage';
import { ChatInput } from '@/components/chat/ChatInput';
import { useConversationStore } from '@/store/conversationStore';
import { useRef, useEffect, memo } from 'react';

const { Title } = Typography;

// 意图按钮类型
interface IntentButton {
  key: string;
  label: string;
  query: string;
}

interface ChatCardProps {
  onSend: (message: string) => void;
  onNewSession?: () => void;
  extra?: React.ReactNode;
  intentButtons?: IntentButton[];
  onIntentClick?: (query: string) => void;
}

export const ChatCard = memo(({
  onSend,
  onNewSession,
  extra,
  intentButtons,
  onIntentClick,
}: ChatCardProps) => {
  const { messages, isLoading } = useConversationStore();
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);

  // 自动滚动到底部
  useEffect(() => {
    if (messagesContainerRef.current) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages]);

  return (
    <div
      style={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        borderRadius: 12,
        boxShadow: '0 4px 12px rgba(0,0,0,0.08)',
        border: '1px solid var(--border-light)',
        background: 'var(--bg-primary)',
        overflow: 'hidden',
      }}
    >
      {/* 标题栏 - 固定高度 */}
      <div
        style={{
          padding: '12px 16px',
          borderBottom: '1px solid var(--border-light)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexShrink: 0,
          background: 'var(--bg-primary)',
        }}
      >
        <Space>
          <RobotOutlined style={{ color: 'var(--color-primary)' }} />
          <span style={{ fontWeight: 500 }}>智能对话助手</span>
          {isLoading && <Badge status="processing" text="处理中" />}
        </Space>
        <Space>
          {extra}
          <Button
            icon={<ClearOutlined />}
            size="small"
            onClick={onNewSession}
            style={{ borderRadius: 6 }}
          >
            新对话
          </Button>
        </Space>
      </div>

      {/* 消息列表区域 - 可滚动，占据剩余空间 */}
      <div
        ref={messagesContainerRef}
        style={{
          flex: '1 1 auto',
          overflowY: 'auto',
          overflowX: 'hidden',
          padding: 16,
          background: 'var(--bg-tertiary)',
          minHeight: 0, // 关键：允许flex子项收缩
        }}
      >
        {messages.length === 0 ? (
          // 空状态
          <div
            style={{
              height: '100%',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--text-tertiary)',
            }}
          >
            <RobotOutlined
              style={{
                fontSize: 48,
                marginBottom: 16,
                color: 'var(--color-primary)',
              }}
            />
            <Title level={4} style={{ margin: 0, color: 'var(--text-primary)' }}>
              开始与智能助手对话
            </Title>
            <p style={{ marginTop: 8, textAlign: 'center' }}>
              您可以查询订单、物流、工单信息
              <br />
              或创建新的工单请求
            </p>
          </div>
        ) : (
          <>
            {messages.map((message) => (
              <ChatMessage key={message.id} message={message} />
            ))}
            <div ref={messagesEndRef} />
          </>
        )}
      </div>

      {/* 快捷意图按钮区域 - 固定高度 */}
      {intentButtons && intentButtons.length > 0 && (
        <div
          style={{
            padding: '10px 16px',
            borderTop: '1px solid var(--border-light)',
            background: 'var(--bg-primary)',
            display: 'flex',
            gap: 8,
            flexWrap: 'wrap',
            flexShrink: 0,
          }}
        >
          {intentButtons.map((btn) => (
            <Button
              key={btn.key}
              size="small"
              onClick={() => onIntentClick?.(btn.query)}
              disabled={isLoading}
              style={{
                borderRadius: 6,
                fontSize: 12,
                padding: '4px 12px',
                height: 'auto',
              }}
            >
              {btn.label}
            </Button>
          ))}
        </div>
      )}

      {/* 输入区域 - 固定高度 */}
      <div
        style={{
          padding: 16,
          borderTop: '1px solid var(--border-light)',
          background: 'var(--bg-primary)',
          flexShrink: 0,
        }}
      >
        <ChatInput onSend={onSend} loading={isLoading} />
      </div>
    </div>
  );
});

ChatCard.displayName = 'ChatCard';

export default ChatCard;
