import apiClient from './client';
import type { ChatRequest, ChatResponse } from '@/types/conversation';

// 后端响应类型
interface BackendProcessResponse {
  success: boolean;
  query: string;
  response: string;
  waiting_for_input?: boolean;
  clarification_prompt?: string;
  session_id: string;
  timestamp: string;
}

export const chatService = {
  // 处理用户查询
  sendMessage: async (content: string, sessionId?: string): Promise<ChatResponse> => {
    const payload: ChatRequest = {
      query: content,
      session_id: sessionId,
    };
    try {
      const response = await apiClient.post('/process', payload) as BackendProcessResponse;
      return {
        success: response.success,
        query: response.query,
        response: response.response,
        session_id: response.session_id,
        timestamp: response.timestamp,
        suggested_actions: [
          { action: 'track', label: '追踪订单' },
        ],
      };
    } catch (error) {
      console.error('发送消息失败:', error);
      return {
        success: false,
        query: content,
        response: '',
        session_id: sessionId || '',
        timestamp: new Date().toISOString(),
        error: {
          code: 'NETWORK_ERROR',
          message: error instanceof Error ? error.message : '网络连接失败',
        },
      };
    }
  },

  // 获取系统状态
  getSystemStatus: async (): Promise<Record<string, unknown> | null> => {
    try {
      return await apiClient.get('/status') as Record<string, unknown>;
    } catch (error) {
      console.error('获取系统状态失败:', error);
      return null;
    }
  },

  // 获取健康检查
  healthCheck: async (): Promise<boolean> => {
    try {
      const response = await apiClient.get('/health') as { status?: string };
      return response?.status === 'healthy';
    } catch {
      return false;
    }
  },
};

export default chatService;
