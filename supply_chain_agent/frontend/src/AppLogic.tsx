import { useCallback } from 'react';
import { message } from 'antd';
import type { AgentEvent } from '@/types/agent';

export const useAppWebSocket = () => {
  const onMessage = useCallback((data: AgentEvent) => {
    console.log('WebSocket message:', data);
  }, []);

  const onConnect = useCallback(() => {
    console.log('WebSocket 已连接');
  }, []);

  const onDisconnect = useCallback(() => {
    console.log('WebSocket 已断开');
  }, []);

  const onError = useCallback((error: Event) => {
    console.error('WebSocket 错误:', error);
    message.error('WebSocket连接失败');
  }, []);

  return { onMessage, onConnect, onDisconnect, onError };
};

export const AppLogic = ({ children }: { children: React.ReactNode }) => {
  return <>{children}</>;
};

export default AppLogic;
