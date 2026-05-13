import { useState, useRef } from 'react';
import { Input, Button } from 'antd';
import { SendOutlined, LoadingOutlined } from '@ant-design/icons';

interface ChatInputProps {
  onSend: (message: string) => void;
  loading?: boolean;
}

export const ChatInput = ({ onSend, loading }: ChatInputProps) => {
  const [input, setInput] = useState('');
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const handleSend = () => {
    if (input.trim() && !loading) {
      onSend(input.trim());
      setInput('');
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div style={{ display: 'flex', gap: 12 }}>
      <Input.TextArea
        ref={inputRef}
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="输入消息，按Enter发送，Shift+Enter换行..."
        autoSize={{ minRows: 2, maxRows: 6 }}
        disabled={loading}
        style={{
          flex: 1,
          fontSize: 14,
          borderRadius: 8,
          background: 'var(--bg-secondary)',
        }}
      />
      <Button
        type="primary"
        icon={loading ? <LoadingOutlined /> : <SendOutlined />}
        onClick={handleSend}
        disabled={!input.trim() || loading}
        loading={loading}
        size="large"
        style={{ height: 'auto' }}
      >
        发送
      </Button>
    </div>
  );
};

export default ChatInput;
