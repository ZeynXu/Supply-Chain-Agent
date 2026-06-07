"""
执行计划生成相关的Prompt模板
"""


APPROVAL_PLAN_PROMPT = """你是一个供应链系统的执行计划生成器。根据以下AGENT.md中定义的审批工单流程，生成执行计划。

## AGENT.md 内容

{agent_md_content}

## 用户请求信息

- 意图: 审批工单
- 提取的实体: {entities}

## 可用工具

以下是系统中可用的工具列表：
1. query_work_order - 查询工单（需要 work_order_id）
2. query_order - 查询订单（需要 order_id）
3. query_customer_statistics - 查询客户统计信息（需要 customer_id）

## 任务

根据AGENT.md中的审批工单流程，生成一个JSON格式的执行计划，包含以下字段：
- tasks: 任务列表，每个任务包含 name（任务名称）、tool（工具名称）、description（任务描述）

请直接输出JSON格式的结果，不要包含其他文字说明。
```json
{{
  "tasks": [
    {{"name": "任务名称", "tool": "工具名称", "description": "任务描述"}}
  ]
}}
```"""


# 工具参数提取Prompt模板
TOOL_PARAM_EXTRACTION_PROMPT = """你是一个供应链系统的参数提取专家。请根据当前工具的执行结果，为下一个工具提取或生成所需的参数。

## 当前执行状态
- 执行计划: {execution_plan}
- 已执行工具: {executed_tools}
- 当前步骤: {current_step}

## 当前工具执行结果
工具名称: {current_tool}
执行结果:
```json
{current_result}
```

## 下一个要执行的工具
工具名称: {next_tool}
必需参数: {required_params}
可选参数: {optional_params}

## 当前已有的槽位信息
```json
{current_slots}
```

## 工具参数说明

### query_work_order
- work_order_id: 工单ID（必需）

### query_order
- order_id: 订单ID（必需）

### query_customer_statistics
- customer_id: 客户ID（必需）

### approve_work_order
- work_order_id: 工单ID（必需）
- action: 审批动作，可选值: approve, reject, escalate（必需）
- comment: 审批备注（可选）
- approver: 审批人（可选）

## 任务
请分析当前工具的执行结果，为下一个工具提取或生成所需的参数。
- 优先从执行结果中提取参数值
- 如果执行结果中没有所需参数，尝试从已有槽位中获取
- 如果是工单查询结果，注意提取 customer_id、order_id 等关联信息
- 只返回下一个工具实际需要的参数

请直接输出JSON格式的结果，格式如下：
```json
{{
  "parameters": {{
    "参数名": "参数值"
  }}
}}
```

注意：
1. 只输出JSON，不要包含其他文字说明
2. 参数值要准确，从执行结果中提取时要保持原始格式
3. 如果某个必需参数无法从结果中获取，可以在parameters中设为null
4. 对于工单查询结果，通常可以从结果中提取 order_id 和 customer_id 用于后续查询"""


# 初始参数生成Prompt模板（用于审批工单流程开始前）
INITIAL_PARAM_GENERATION_PROMPT = """你是一个供应链系统的参数生成专家。请根据用户的审批工单请求，生成执行计划所需的初始参数。

## 用户请求信息
- 意图: {intent}
- 提取的实体: {entities}

## 执行计划
{execution_plan}

## 第一个要执行的工具
工具名称: {first_tool}
必需参数: {required_params}

## 任务
请分析用户请求和提取的实体，为第一个工具生成所需的参数。
- 从实体中提取参数值
- 如果实体中没有所需参数，尝试推断或使用默认值

请直接输出JSON格式的结果，格式如下：
```json
{{
  "parameters": {{
    "参数名": "参数值"
  }}
}}
```"""


# ============================================
# 审批分析Prompt模板（精简版）
# ============================================

APPROVAL_ANALYSIS_PROMPT = """你是供应链审批专家。根据查询结果和规则，给出审批建议。

## 工单: {work_order_id}

## 查询结果

**工单**: {work_order_result}

**订单**: {order_result}

**客户**: {customer_statistics_result}

## 审批规则

### 客商风险等级
- A级(优质): 企业客户，履约良好，额度>50000
- B级(良好): 企业客户，偶有延迟，额度20000-50000
- C级(一般): 个人客户，额度5000-20000
- D级(关注): 多次延迟或有取消记录，额度2000-5000
- E级(高风险): 频繁取消或欺诈风险，额度<2000

### 审批权限
- 金额≤2000且A/B/C级 → 业务主管
- 金额2001-10000或D级 → 运营负责人
- 金额10001-50000或E级 → 部门负责人
- 金额>50000或超额>20% → 风控特别审批

{sop_customer_classification}

## 输出要求

输出JSON:
```json
{{
  "summary": "一句话概况",
  "risk_level": "A/B/C/D/E级",
  "risk_factors": ["风险因素"],
  "approval_level": "审批层级",
  "recommendation": {{
    "action": "approve/reject/escalate",
    "reason": "理由"
  }},
  "confidence": 0.85
}}
```"""
