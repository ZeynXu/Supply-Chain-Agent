import { Avatar, Space, Tag, Button, Typography } from 'antd';
import { UserOutlined, RobotOutlined, CopyOutlined, CheckOutlined } from '@ant-design/icons';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useState, memo } from 'react';
import type { Message } from '@/types/conversation';

const { Text } = Typography;

interface ChatMessageProps {
  message: Message;
}

export const ChatMessage = memo(({ message }: ChatMessageProps) => {
  const [copied, setCopied] = useState(false);
  const isUser = message.role === 'user';
  const isLoading = message.status === 'sending' || message.status === 'streaming';

  const handleCopy = () => {
    navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // 格式化时间
  const formatTime = (timestamp: string) => {
    const date = new Date(timestamp);
    return date.toLocaleTimeString('zh-CN', {
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <div
      style={{
        display: 'flex',
        gap: 12,
        marginBottom: 24,
        flexDirection: isUser ? 'row-reverse' : 'row',
      }}
      className="message-enter"
    >
      {/* 头像 */}
      <Avatar
        icon={isUser ? <UserOutlined /> : <RobotOutlined />}
        style={{
          backgroundColor: isUser ? 'var(--color-primary)' : '#52c41a',
          flexShrink: 0,
        }}
      />

      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: isUser ? 'flex-end' : 'flex-start',
          maxWidth: '80%',
        }}
      >
        {/* 用户名和时间 */}
        <Space style={{ marginBottom: 4 }}>
          <Text strong style={{ fontSize: 13 }}>
            {isUser ? '我' : '智能助手'}
          </Text>
          <Text type="secondary" style={{ fontSize: 11 }}>
            {formatTime(message.timestamp)}
          </Text>
        </Space>

        {/* 用户消息气泡 */}
        {isUser ? (
          <div
            className="chat-bubble-user"
            style={{
              padding: '12px 16px',
              background: 'linear-gradient(135deg, var(--color-primary) 0%, var(--color-primary-dark) 100%)',
              color: 'white',
              borderRadius: '16px 16px 4px 16px',
              lineHeight: 1.6,
              wordBreak: 'break-word',
            }}
          >
            {message.content}
          </div>
        ) : (
          <>
            {/* 加载状态 */}
            {isLoading ? (
              <div
                className="chat-bubble-assistant"
                style={{
                  padding: 16,
                  background: 'var(--bg-secondary)',
                  borderRadius: '16px 16px 16px 4px',
                  minWidth: 100,
                }}
              >
                <Space>
                  <span className="pulse-animation">思考中...</span>
                </Space>
              </div>
            ) : (
              /* 助手消息气泡 */
              <div
                className="chat-bubble-assistant"
                style={{
                  padding: 16,
                  background: 'var(--bg-secondary)',
                  borderRadius: '16px 16px 16px 4px',
                  lineHeight: 1.8,
                  border: '1px solid var(--border-light)',
                }}
              >
                {/* Markdown 内容 */}
                <div className="markdown-content">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {message.content}
                  </ReactMarkdown>
                </div>

                {/* 数据卡片 */}
                {message.dataCards && message.dataCards.length > 0 && (
                  <div
                    style={{
                      marginTop: 12,
                      display: 'flex',
                      gap: 8,
                      flexWrap: 'wrap',
                    }}
                  >
                    {message.dataCards.map((card, idx) => (
                      <div
                        key={idx}
                        style={{
                          padding: '8px 12px',
                          border: '1px solid var(--border-color)',
                          borderRadius: 6,
                          minWidth: 120,
                          textAlign: 'center',
                          background: 'var(--bg-primary)',
                        }}
                      >
                        <div
                          style={{
                            fontSize: 11,
                            color: 'var(--text-tertiary)',
                          }}
                        >
                          {card.label}
                        </div>
                        <div
                          style={{
                            fontSize: 16,
                            color: 'var(--color-primary)',
                            fontWeight: 600,
                          }}
                        >
                          {card.value}
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {/* 建议操作 */}
                {message.suggestedActions && message.suggestedActions.length > 0 && (
                  <div style={{ marginTop: 12 }}>
                    <Text type="secondary" style={{ fontSize: 11 }}>
                      建议操作:
                    </Text>
                    <div style={{ marginTop: 4, display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                      {message.suggestedActions.map((action, idx) => (
                        <Tag
                          key={idx}
                          color="blue"
                          style={{
                            cursor: 'pointer',
                            borderRadius: 4,
                          }}
                        >
                          {action.label}
                        </Tag>
                      ))}
                    </div>
                  </div>
                )}

                {/* 复制按钮 */}
                {message.content && (
                  <div style={{ marginTop: 8 }}>
                    <Button
                      type="text"
                      size="small"
                      icon={copied ? <CheckOutlined /> : <CopyOutlined />}
                      onClick={handleCopy}
                      style={{
                        color: copied ? '#52c41a' : 'var(--text-tertiary)',
                        padding: '0 8px',
                      }}
                    >
                      {copied ? '已复制' : '复制'}
                    </Button>
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
});

ChatMessage.displayName = 'ChatMessage';

export default ChatMessage;
