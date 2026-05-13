import type { AgentEvent } from '@/types/agent';

export const mockAgentEvents = (query: string): AgentEvent[] => {
  const events: AgentEvent[] = [
    {
      type: 'step_start',
      timestamp: Date.now(),
      data: {
        stepId: 'step-1',
        agentType: 'parse_input',
        title: '意图识别',
        description: '分析用户查询意图',
        raw: { query },
      },
    },
    {
      type: 'step_end',
      timestamp: Date.now() + 200,
      data: {
        stepId: 'step-1',
        agentType: 'parse_input',
        title: '意图识别完成',
        description: '识别为状态查询-物流查询意图',
        raw: { intent: '物流查询', confidence: 0.95 },
      },
    },
    {
      type: 'step_start',
      timestamp: Date.now() + 300,
      data: {
        stepId: 'step-2',
        agentType: 'plan_task',
        title: '任务规划',
        description: '制定执行计划',
      },
    },
    {
      type: 'step_end',
      timestamp: Date.now() + 400,
      data: {
        stepId: 'step-2',
        agentType: 'plan_task',
        title: '任务规划完成',
        description: '已创建执行计划',
      },
    },
    {
      type: 'step_start',
      timestamp: Date.now() + 500,
      data: {
        stepId: 'step-3',
        agentType: 'execute_task',
        title: '执行工具调用',
        description: '查询订单状态和物流信息',
      },
    },
    {
      type: 'tool_call',
      timestamp: Date.now() + 600,
      data: {
        toolCall: {
          id: 'tool-1',
          name: 'query_order_status',
          parameters: { order_id: 'PO-2026-001' },
          startTime: Date.now() + 600,
          status: 'running',
        },
      },
    },
    {
      type: 'tool_result',
      timestamp: Date.now() + 1000,
      data: {
        toolCall: {
          id: 'tool-1',
          name: 'query_order_status',
          parameters: { order_id: 'PO-2026-001' },
          response: {
            order_id: 'PO-2026-001',
            status: '待收货',
            amount: 12500.0,
            supplier: 'XX科技',
          },
          startTime: Date.now() + 600,
          endTime: Date.now() + 1000,
          status: 'success',
        },
      },
    },
    {
      type: 'tool_call',
      timestamp: Date.now() + 1100,
      data: {
        toolCall: {
          id: 'tool-2',
          name: 'get_logistics_trace',
          parameters: { tracking_no: 'SF123456789' },
          startTime: Date.now() + 1100,
          status: 'running',
        },
      },
    },
    {
      type: 'tool_result',
      timestamp: Date.now() + 1700,
      data: {
        toolCall: {
          id: 'tool-2',
          name: 'get_logistics_trace',
          parameters: { tracking_no: 'SF123456789' },
          response: {
            tracking_no: 'SF123456789',
            status: '运输中',
            current_location: '厦门集散中心',
            estimated_delivery: '今日18:00前',
          },
          startTime: Date.now() + 1100,
          endTime: Date.now() + 1700,
          status: 'success',
        },
      },
    },
    {
      type: 'step_end',
      timestamp: Date.now() + 1800,
      data: {
        stepId: 'step-3',
        agentType: 'execute_task',
        title: '工具调用完成',
        description: '成功获取订单和物流信息',
      },
    },
    {
      type: 'step_start',
      timestamp: Date.now() + 1900,
      data: {
        stepId: 'step-4',
        agentType: 'audit',
        title: '结果校验',
        description: '验证处理结果的准确性和完整性',
      },
    },
    {
      type: 'step_end',
      timestamp: Date.now() + 2100,
      data: {
        stepId: 'step-4',
        agentType: 'audit',
        title: '校验通过',
        description: '结果验证成功',
      },
    },
    {
      type: 'step_start',
      timestamp: Date.now() + 2200,
      data: {
        stepId: 'step-5',
        agentType: 'generate_report',
        title: '生成响应',
        description: '生成最终响应报告',
      },
    },
    {
      type: 'step_end',
      timestamp: Date.now() + 2400,
      data: {
        stepId: 'step-5',
        agentType: 'generate_report',
        title: '响应生成完成',
        description: '已生成最终响应',
      },
    },
    {
      type: 'complete',
      timestamp: Date.now() + 2500,
      data: {
        raw: {
          response: '订单PO-2026-001当前位于厦门集散中心，预计今日18:00前派送。承运商：顺丰快递，运单号：SF123456789。',
        }
      },
    },
  ];

  return events;
};
