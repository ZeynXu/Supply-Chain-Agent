import { useCallback, useRef } from 'react';
import { useWebSocket } from './useWebSocket';
import { useUIStore } from '@/store/uiStore';
import { useConversationStore } from '@/store/conversationStore';
import type { AgentEvent } from '@/types/agent';

export const useAgentEvents = () => {
  const { wsUrl, setWsConnected } = useUIStore();
  const {
    initAgentTrajectory,
    handleAgentEvent,
    completeAgentTrajectory,
    addMessage,
    sessionId,
  } = useConversationStore();

  const isConnectedRef = useRef(false);

  const onMessage = useCallback((data: AgentEvent) => {
    handleAgentEvent(data);

    switch (data.type) {
      case 'complete':
        completeAgentTrajectory();
        if (data.data.raw?.response) {
          addMessage({
            role: 'assistant',
            content: data.data.raw.response as string,
            status: 'success',
          });
        }
        break;

      case 'error':
        addMessage({
          role: 'assistant',
          content: data.data.error || '处理过程中发生错误',
          status: 'error',
        });
        break;
    }
  }, [handleAgentEvent, completeAgentTrajectory, addMessage]);

  const onConnect = useCallback(() => {
    console.log('[AgentEvents] WebSocket 已连接');
    isConnectedRef.current = true;
    setWsConnected(true);
  }, [setWsConnected]);

  const onDisconnect = useCallback(() => {
    console.log('[AgentEvents] WebSocket 已断开');
    isConnectedRef.current = false;
    setWsConnected(false);
  }, [setWsConnected]);

  const onError = useCallback((error: Event) => {
    console.error('[AgentEvents] WebSocket 错误:', error);
    isConnectedRef.current = false;
    setWsConnected(false);
  }, [setWsConnected]);

  // 构建WebSocket URL
  const fullWsUrl = `${wsUrl}/process`.replace('://', '://').replace(/\/\//g, '/');

  const ws = useWebSocket({
    url: fullWsUrl,
    onMessage,
    onConnect,
    onDisconnect,
    onError,
    reconnectAttempts: 5,
    reconnectInterval: 3000,
    autoConnect: false, // 不自动连接，由用户触发或手动控制
  });

  // 发送查询
  const sendQuery = useCallback((query: string) => {
    if (!ws.connected) {
      console.warn('[AgentEvents] WebSocket 未连接，尝试连接...');
      ws.reconnect();
      // 延迟发送
      setTimeout(() => {
        if (ws.connected) {
          ws.sendMessage({
            query,
            session_id: sessionId,
          });
          initAgentTrajectory(sessionId);
          // 发送总控节点开始事件
          handleAgentEvent({
            type: 'step_start',
            timestamp: Date.now(),
            data: {
              stepId: 'orchestrator-main',
              agentType: 'orchestrator',
              title: '处理请求',
              description: '总控节点正在处理您的请求...'
            },
          });
        }
      }, 1000);
      return;
    }

    ws.sendMessage({
      query,
      session_id: sessionId,
    });
    initAgentTrajectory(sessionId);
    // 发送总控节点开始事件
    handleAgentEvent({
      type: 'step_start',
      timestamp: Date.now(),
      data: {
        stepId: 'orchestrator-main',
        agentType: 'orchestrator',
        title: '处理请求',
        description: '总控节点正在处理您的请求...'
      },
    });
  }, [ws, sessionId, initAgentTrajectory, handleAgentEvent]);

  return {
    ...ws,
    sendQuery,
    isConnected: ws.connected,
    isConnecting: ws.connecting,
  };
};

export default useAgentEvents;
