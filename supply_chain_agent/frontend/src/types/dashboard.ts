// dashboard.ts - 仪表板相关类型定义

export interface DashboardStats {
  totalWorkorders: number;
  avgProcessingTime: number;
  automationRate: number;
  toolSuccessRate: number;
}

export interface TrendData {
  date: string;
  count: number;
}

export interface WorkorderDistribution {
  type: string;
  count: number;
  percentage: number;
}

export interface WorkorderQueueItem {
  id: string;
  summary: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  processingTime: number;
  createdAt: string;
}

export interface SystemMetrics {
  period: string;
  granularity: string;
  metrics: {
    requests: {
      total: number;
      successful: number;
      failed: number;
      successRate: number;
    };
    responseTimes: {
      avg: number;
      p50: number;
      p95: number;
      p99: number;
      max: number;
    };
    intents: Record<string, number>;
    tools: Record<string, {
      calls: number;
      successRate: number;
      avgTime: number;
    }>;
  };
  timestamps: string[];
}
