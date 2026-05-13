// agent.ts - Agent执行轨迹相关类型定义

export type AgentType = 'orchestrator' | 'parse_input' | 'clarify' | 'plan_task' | 'execute_task' | 'retry' | 'audit' | 'generate_report' | 'handle_error';

export type StepStatus = 'pending' | 'running' | 'success' | 'error' | 'warning';

export interface ToolCall {
  id: string;
  name: string;
  parameters: Record<string, unknown>;
  response?: Record<string, unknown>;
  error?: string;
  startTime: number;
  endTime?: number;
  status: StepStatus;
}

export interface AgentStep {
  id: string;
  agentType: AgentType;
  title: string;
  description: string;
  status: StepStatus;
  startTime: number;
  endTime?: number;
  tools: ToolCall[];
  rawData?: Record<string, unknown>;
}

export interface AgentTrajectory {
  sessionId: string;
  steps: AgentStep[];
  currentStepId?: string;
  overallStatus: StepStatus;
  startTime: number;
  endTime?: number;
}

export interface AgentEvent {
  type: 'step_start' | 'step_end' | 'tool_call' | 'tool_result' | 'error' | 'complete';
  timestamp: number;
  data: {
    stepId?: string;
    agentType?: AgentType;
    title?: string;
    description?: string;
    toolCall?: ToolCall;
    error?: string;
    raw?: Record<string, unknown>;
  };
}

// Agent类型到显示名称的映射
export const AGENT_TYPE_LABELS: Record<AgentType, string> = {
  orchestrator: '总控',
  parse_input: '解析师',
  clarify: '澄清',
  plan_task: '任务规划',
  execute_task: '执行器',
  retry: '重试处理',
  audit: '审计员',
  generate_report: '报告生成',
  handle_error: '错误处理',
};

// Agent类型到颜色的映射
export const AGENT_TYPE_COLORS: Record<AgentType, string> = {
  orchestrator: 'purple',
  parse_input: 'blue',
  clarify: 'cyan',
  plan_task: 'geekblue',
  execute_task: 'green',
  retry: 'orange',
  audit: 'gold',
  generate_report: 'magenta',
  handle_error: 'red',
};

// Agent所属层级映射
export const AGENT_LAYER_MAP: Record<AgentType, string> = {
  orchestrator: '主控层',
  parse_input: 'ParserAgent层',
  clarify: 'ParserAgent层',
  plan_task: 'ExecutorAgent层',
  execute_task: 'ExecutorAgent层',
  retry: '独立节点层',
  audit: 'AuditorAgent层',
  generate_report: 'ReportGenerator层',
  handle_error: '独立节点层',
};
