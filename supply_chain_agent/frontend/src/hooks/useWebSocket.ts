import { useState, useRef, useCallback, useEffect } from 'react';
import type { AgentEvent } from '@/types/agent';

interface WebSocketOptions {
  url: string;
  onMessage?: (data: AgentEvent) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
  onError?: (error: Event) => void;
  reconnectAttempts?: number;
  reconnectInterval?: number;
  autoConnect?: boolean;
}

interface WebSocketHookReturn {
  connected: boolean;
  connecting: boolean;
  sendMessage: (data: Record<string, unknown>) => void;
  reconnect: () => void;
  disconnect: () => void;
}

export const useWebSocket = (options: WebSocketOptions): WebSocketHookReturn => {
  const {
    url,
    onMessage,
    onConnect,
    onDisconnect,
    onError,
    reconnectAttempts = 5,
    reconnectInterval = 3000,
    autoConnect = true,
  } = options;

  const [connected, setConnected] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectCountRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mountedRef = useRef(true);
  const shouldReconnectRef = useRef(true);

  // 清理重连定时器
  const clearReconnectTimer = useCallback(() => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
  }, []);

  // 断开连接
  const disconnect = useCallback(() => {
    shouldReconnectRef.current = false;
    clearReconnectTimer();
    if (wsRef.current) {
      wsRef.current.close(1000, 'User disconnect');
      wsRef.current = null;
    }
    setConnected(false);
    setConnecting(false);
  }, [clearReconnectTimer]);

  // 连接WebSocket
  const connect = useCallback(() => {
    // 如果已经连接或正在连接，直接返回
    if (wsRef.current?.readyState === WebSocket.OPEN || wsRef.current?.readyState === WebSocket.CONNECTING) {
      return;
    }

    // 清理旧连接
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    shouldReconnectRef.current = true;
    setConnecting(true);
    setConnected(false);

    try {
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        if (!mountedRef.current) return;
        setConnected(true);
        setConnecting(false);
        reconnectCountRef.current = 0;
        console.log('[WebSocket] 已连接:', url);
        onConnect?.();
      };

      ws.onmessage = (event) => {
        if (!mountedRef.current) return;
        try {
          const data = JSON.parse(event.data) as AgentEvent;
          onMessage?.(data);
        } catch (err) {
          console.error('[WebSocket] 解析消息失败:', err);
        }
      };

      ws.onclose = (event) => {
        if (!mountedRef.current) return;
        setConnected(false);
        setConnecting(false);
        wsRef.current = null;
        console.log('[WebSocket] 连接关闭:', event.code, event.reason);
        onDisconnect?.();

        // 非正常关闭且需要重连时尝试重连
        if (
          shouldReconnectRef.current &&
          event.code !== 1000 &&
          reconnectCountRef.current < reconnectAttempts
        ) {
          reconnectCountRef.current += 1;
          console.log(`[WebSocket] 重连中... (${reconnectCountRef.current}/${reconnectAttempts})`);
          reconnectTimerRef.current = setTimeout(() => {
            if (mountedRef.current && shouldReconnectRef.current) {
              connect();
            }
          }, reconnectInterval);
        }
      };

      ws.onerror = (error) => {
        if (!mountedRef.current) return;
        console.error('[WebSocket] 连接错误:', error);
        setConnecting(false);
        onError?.(error);
      };
    } catch (err) {
      console.error('[WebSocket] 创建连接失败:', err);
      setConnecting(false);
      setConnected(false);
    }
  }, [url, onMessage, onConnect, onDisconnect, onError, reconnectAttempts, reconnectInterval]);

  // 发送消息
  const sendMessage = useCallback((data: Record<string, unknown>) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data));
    } else {
      console.warn('[WebSocket] 未连接，无法发送消息');
    }
  }, []);

  // 手动重连
  const reconnect = useCallback(() => {
    console.log('[WebSocket] 触发手动重连');
    shouldReconnectRef.current = true;
    reconnectCountRef.current = 0;
    clearReconnectTimer();

    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setConnected(false);
    setConnecting(false);

    // 延迟后重新连接
    setTimeout(() => {
      if (mountedRef.current) {
        connect();
      }
    }, 100);
  }, [connect, clearReconnectTimer]);

  // 自动连接
  useEffect(() => {
    mountedRef.current = true;

    if (autoConnect && url) {
      connect();
    }

    return () => {
      mountedRef.current = false;
      shouldReconnectRef.current = false;
      clearReconnectTimer();
      if (wsRef.current) {
        wsRef.current.close(1000, 'Component unmount');
        wsRef.current = null;
      }
    };
  }, [autoConnect, url, connect, clearReconnectTimer]);

  return {
    connected,
    connecting,
    sendMessage,
    reconnect,
    disconnect,
  };
};

export default useWebSocket;
