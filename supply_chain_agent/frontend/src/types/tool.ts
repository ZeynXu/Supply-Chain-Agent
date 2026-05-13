// tool.ts - 工具管理相关类型定义

export interface ToolParameter {
  name: string;
  type: 'string' | 'number' | 'boolean' | 'array' | 'object';
  required: boolean;
  description: string;
  default?: unknown;
  enum?: string[];
}

export interface Tool {
  name: string;
  description: string;
  parameters: ToolParameter[];
  status: 'available' | 'unavailable' | 'deprecated';
  requiresConfirmation?: boolean;
  health?: {
    successRate: number;
    avgResponseTime: number;
    lastChecked: string;
  };
  callCount?: number;
  failCount?: number;
}

export interface ToolTestRequest {
  toolName: string;
  parameters: Record<string, unknown>;
}

export interface ToolTestResponse {
  tool: string;
  success: boolean;
  response?: Record<string, unknown>;
  error?: string;
  responseTime: number;
  timestamp: string;
}

export interface ToolMetrics {
  name: string;
  calls: number;
  successRate: number;
  avgTime: number;
  failRate: number;
}
