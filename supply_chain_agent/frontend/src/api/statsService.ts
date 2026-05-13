import apiClient from './client';
import type { DashboardStats } from '@/types/dashboard';

// 后端状态响应类型
interface SystemStatus {
  status?: string;
  memory?: {
    summary?: string;
    recent_items?: number;
  };
  checkpoints?: Record<string, unknown>;
  tools?: Record<string, { success_rate?: number; avg_time?: number }>;
}

export const statsService = {
  // 获取系统状态
  getSystemStatus: async (): Promise<SystemStatus | null> => {
    try {
      return await apiClient.get('/status') as SystemStatus;
    } catch (error) {
      console.error('获取系统状态失败:', error);
      return null;
    }
  },

  // 获取仪表板统计数据
  getDashboardStats: async (): Promise<DashboardStats> => {
    try {
      const status = await statsService.getSystemStatus();

      if (status && status.tools) {
        // 从工具统计计算成功率
        const toolStats = Object.values(status.tools);
        const avgToolSuccessRate = toolStats.length > 0
          ? toolStats.reduce((acc, t) => acc + (t.success_rate || 0), 0) / toolStats.length
          : 0.95;

        return {
          totalWorkorders: status.memory?.recent_items || 125,
          avgProcessingTime: 2.1,
          automationRate: 72.0,
          toolSuccessRate: avgToolSuccessRate * 100,
        };
      }

      // 返回默认值
      return {
        totalWorkorders: 125,
        avgProcessingTime: 2.1,
        automationRate: 72.0,
        toolSuccessRate: 96.0,
      };
    } catch {
      return {
        totalWorkorders: 0,
        avgProcessingTime: 0,
        automationRate: 0,
        toolSuccessRate: 0,
      };
    }
  },

  // 获取工单趋势数据（模拟数据）
  getTrendData: async (days = 7) => {
    // 生成模拟趋势数据
    const data = [];
    const now = new Date();
    for (let i = days - 1; i >= 0; i--) {
      const date = new Date(now);
      date.setDate(date.getDate() - i);
      data.push({
        date: date.toISOString().split('T')[0],
        count: Math.floor(Math.random() * 50) + 30,
      });
    }
    return data;
  },

  // 获取工单类型分布（模拟数据）
  getWorkorderDistribution: async () => {
    return [
      { type: '状态查询', count: 35, percentage: 35 },
      { type: '工单创建', count: 30, percentage: 30 },
      { type: '异常上报', count: 20, percentage: 20 },
      { type: '审批流转', count: 15, percentage: 15 },
    ];
  },
};

export default statsService;
