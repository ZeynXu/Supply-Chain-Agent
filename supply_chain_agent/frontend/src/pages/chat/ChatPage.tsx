import { useState, useEffect, useCallback } from 'react';
import { Drawer, Button, message } from 'antd';
import { RightOutlined } from '@ant-design/icons';
import { ChatCard } from '@/components/chat/ChatCard';
import { AgentTrajectoryPanel } from '@/components/agent/AgentTrajectory';
import { useConversationStore } from '@/store/conversationStore';
import { useChat } from '@/hooks/useChat';

// 四种意图快捷按钮配置
const intentButtons = [
  {
    key: 'status_query',
    label: '状态查询',
    query: '查一下PO-2026-001的货到哪了？',
  },
  {
    key: 'workorder_create',
    label: '工单创建',
    query: '创建一个质量检验工单，订单PO-2026-001需要检验',
  },
  {
    key: 'issue_report',
    label: '异常上报',
    query: '报告物流延迟问题，订单PO-2026-002预计延迟3天',
  },
  {
    key: 'approval_flow',
    label: '审批流转',
    query: '审批工单WO-2026-001，理由：质量合格',
  },
];

export const ChatPage = () => {
  const { agentTrajectory } = useConversationStore();
  const { processMessage, newSession } = useChat();
  const [isMobile, setIsMobile] = useState(false);
  const [trajectoryDrawerVisible, setTrajectoryDrawerVisible] = useState(false);

  // 响应式检测
  useEffect(() => {
    const checkWidth = () => {
      setIsMobile(window.innerWidth < 1280);
    };
    checkWidth();
    window.addEventListener('resize', checkWidth);
    return () => window.removeEventListener('resize', checkWidth);
  }, []);

  const handleSend = useCallback(async (content: string) => {
    if (!content.trim()) return;
    await processMessage(content);
  }, [processMessage]);

  const handleNewSession = useCallback(() => {
    newSession();
    message.success('已创建新对话');
  }, [newSession]);

  // 快捷按钮点击处理
  const handleIntentClick = useCallback((query: string) => {
    handleSend(query);
  }, [handleSend]);

  // 渲染轨迹面板内容
  const trajectoryContent = (
    <AgentTrajectoryPanel trajectory={agentTrajectory} />
  );

  // 移动端布局
  if (isMobile) {
    return (
      <div
        style={{
          position: 'fixed',
          top: 56, // 顶部工具栏高度
          left: 0,
          right: 0,
          bottom: 0,
          display: 'flex',
          flexDirection: 'column',
          background: 'var(--bg-tertiary)',
        }}
      >
        {/* 聊天区域 - 填满剩余空间 */}
        <ChatCard
          onSend={handleSend}
          onNewSession={handleNewSession}
          intentButtons={intentButtons}
          onIntentClick={handleIntentClick}
          extra={
            <Button
              type="primary"
              icon={<RightOutlined />}
              onClick={() => setTrajectoryDrawerVisible(true)}
              style={{ borderRadius: 6 }}
            >
              轨迹
            </Button>
          }
        />

        {/* 轨迹抽屉 */}
        <Drawer
          title="Agent 执行轨迹"
          placement="right"
          onClose={() => setTrajectoryDrawerVisible(false)}
          open={trajectoryDrawerVisible}
          width={360}
          styles={{
            body: { padding: 0 },
          }}
        >
          {trajectoryContent}
        </Drawer>
      </div>
    );
  }

  // 桌面端布局 - 固定布局
  return (
    <div
      style={{
        position: 'fixed',
        top: 56, // 顶部工具栏高度
        left: 0,
        right: 0,
        bottom: 0,
        display: 'flex',
        padding: 16,
        gap: 16,
        background: 'var(--bg-tertiary)',
      }}
    >
      {/* 左侧对话区 - 占据剩余空间 */}
      <div
        style={{
          flex: '1 1 auto',
          minWidth: 0,
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        <ChatCard
          onSend={handleSend}
          onNewSession={handleNewSession}
          intentButtons={intentButtons}
          onIntentClick={handleIntentClick}
        />
      </div>

      {/* 右侧轨迹面板 - 固定宽度 */}
      <div
        style={{
          width: 320,
          flexShrink: 0,
          borderRadius: 12,
          boxShadow: '0 4px 12px rgba(0,0,0,0.08)',
          overflow: 'hidden',
          background: 'var(--bg-secondary)',
          border: '1px solid var(--border-light)',
        }}
      >
        {trajectoryContent}
      </div>
    </div>
  );
};

export default ChatPage;
