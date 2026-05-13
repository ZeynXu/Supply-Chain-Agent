import { useCallback, useRef } from 'react';
import { useConversationStore } from '@/store/conversationStore';
import { useUIStore } from '@/store/uiStore';
import { mockAgentEvents } from '@/api/mock/chatMock';
import { chatService } from '@/api/chatService';

export const useChat = () => {
  const { useMock, sessionId } = useConversationStore();
  const { setWsConnected, wsUrl } = useUIStore();

  const addMessage = useConversationStore((state) => state.addMessage);
  const updateLastMessage = useConversationStore((state) => state.updateLastMessage);
  const setLoading = useConversationStore((state) => state.setLoading);
  const initAgentTrajectory = useConversationStore((state) => state.initAgentTrajectory);
  const handleAgentEvent = useConversationStore((state) => state.handleAgentEvent);
  const completeAgentTrajectory = useConversationStore((state) => state.completeAgentTrajectory);
  const newSession = useConversationStore((state) => state.newSession);

  const wsRef = useRef<WebSocket | null>(null);

  const processMessage = useCallback(async (content: string) => {
    setLoading(true);
    initAgentTrajectory(sessionId);

    // 添加用户消息
    addMessage({ role: 'user', content });

    // 添加待响应的助手消息
    addMessage({
      role: 'assistant',
      content: '',
      status: 'sending',
    });

    // 始终先发送总控节点开始事件
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

    if (useMock) {
      // 使用模拟数据
      setWsConnected(true);
      const events = mockAgentEvents(content);
      let responseText = '';

      for (const event of events) {
        await new Promise((resolve) => setTimeout(resolve, 200));
        handleAgentEvent(event);

        if (event.type === 'complete') {
          responseText = (event.data.raw?.response as string) || '处理完成';
        }
      }

      updateLastMessage(responseText, undefined, [
        { action: 'track', label: '追踪订单' },
      ]);
    } else {
      // 真实API调用 - 使用WebSocket
      try {
        // 先检查健康状态
        const isHealthy = await chatService.healthCheck();
        setWsConnected(isHealthy);

        if (!isHealthy) {
          // 更新总控节点状态为错误
          handleAgentEvent({
            type: 'step_end',
            timestamp: Date.now(),
            data: { stepId: 'orchestrator-main' },
          });
          updateLastMessage('抱歉，无法连接到后端服务。请检查服务是否已启动，或在设置中开启 Mock 模式进行测试。');
          setLoading(false);
          completeAgentTrajectory();
          return;
        }

        // 使用WebSocket连接
        const fullWsUrl = `${wsUrl}/ws/process`.replace('http://', 'ws://').replace('https://', 'wss://');

        await new Promise<void>((resolve, reject) => {
          const ws = new WebSocket(fullWsUrl);
          wsRef.current = ws;
          let resolved = false;

          ws.onopen = () => {
            console.log('[WebSocket] 已连接:', fullWsUrl);
            setWsConnected(true);
            // 发送查询
            ws.send(JSON.stringify({
              query: content,
              session_id: sessionId,
            }));
          };

          ws.onmessage = (event) => {
            try {
              const data = JSON.parse(event.data);
              console.log('[WebSocket] 收到消息:', data.type, data.data?.agentType || '');

              // 处理Agent事件
              if (data.type && data.timestamp && data.data) {
                handleAgentEvent({
                  type: data.type,
                  timestamp: data.timestamp,
                  data: data.data,
                });

                // 处理完成事件
                if (data.type === 'complete') {
                  const response = data.data?.raw?.response || '处理完成';
                  updateLastMessage(response, undefined, [
                    { action: 'track', label: '追踪订单' },
                  ]);

                  if (!resolved) {
                    resolved = true;
                    resolve();
                  }
                }

                // 处理错误事件
                if (data.type === 'error') {
                  const errorMsg = data.data?.error || '处理失败';
                  updateLastMessage(`抱歉，处理时发生错误: ${errorMsg}`);

                  if (!resolved) {
                    resolved = true;
                    resolve();
                  }
                }
              }
            } catch (err) {
              console.error('[WebSocket] 解析消息失败:', err);
            }
          };

          ws.onerror = (error) => {
            console.error('[WebSocket] 连接错误:', error);
            setWsConnected(false);
            if (!resolved) {
              resolved = true;
              reject(error);
            }
          };

          ws.onclose = (event) => {
            console.log('[WebSocket] 连接关闭:', event.code, event.reason);
            setWsConnected(false);
            wsRef.current = null;
            if (!resolved) {
              resolved = true;
              resolve(); // 即使关闭也resolve，避免挂起
            }
          };

          // 设置超时
          setTimeout(() => {
            if (!resolved) {
              resolved = true;
              ws.close();
              resolve();
            }
          }, 60000); // 60秒超时
        });

      } catch (error) {
        setWsConnected(false);
        console.error('Chat error:', error);
        // 更新总控节点状态为错误
        handleAgentEvent({
          type: 'step_end',
          timestamp: Date.now(),
          data: { stepId: 'orchestrator-main' },
        });
        updateLastMessage('抱歉，处理您的请求时出现错误。请检查网络连接或稍后重试。');
      }
    }

    completeAgentTrajectory();
    setLoading(false);
  }, [
    useMock,
    sessionId,
    wsUrl,
    addMessage,
    updateLastMessage,
    setLoading,
    initAgentTrajectory,
    handleAgentEvent,
    completeAgentTrajectory,
    setWsConnected,
  ]);

  return {
    processMessage,
    newSession,
  };
};

export default useChat;
