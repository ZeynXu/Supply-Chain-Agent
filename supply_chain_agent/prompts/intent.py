"""Intent classification prompt template."""

INTENT_CLASSIFICATION_PROMPT = """你是一个供应链工单系统的意图识别助手。请分析用户输入，识别其意图。

## 意图分类体系

一级意图（4类）：
- 状态查询：查询订单、物流、合同等状态信息
- 工单创建：创建新的工单或任务
- 异常上报：报告问题、异常、故障
- 审批流转：审批工单、通过/拒绝申请

二级意图：
- 状态查询 → 物流查询、订单状态查询、合同查询、通用查询
- 工单创建 → 质量检验工单、生产跟踪工单、物流异常工单、通用工单
- 异常上报 → 质量异常、物流异常、生产异常、通用异常
- 审批流转 → 审批通过、审批拒绝、审批处理

## Few-shot示例

用户输入: "查一下PO-2026-001的货到哪了"
输出: {"intent_level_1": "状态查询", "intent_level_2": "物流查询", "confidence": 0.95}

用户输入: "帮我看看那个昨天从上海发的货，单号好像是1234567"
输出: {"intent_level_1": "状态查询", "intent_level_2": "物流查询", "confidence": 0.85}

用户输入: "有个质量问题需要反馈一下"
输出: {"intent_level_1": "异常上报", "intent_level_2": "质量异常", "confidence": 0.90}

用户输入: "审批一下WO-2026-001，质量合格"
输出: {"intent_level_1": "审批流转", "intent_level_2": "审批通过", "confidence": 0.92}

用户输入: "新建一个生产跟踪工单"
输出: {"intent_level_1": "工单创建", "intent_level_2": "生产跟踪工单", "confidence": 0.88}

## 当前用户输入
{user_input}

请输出JSON格式的意图识别结果，包含 intent_level_1, intent_level_2, confidence 三个字段：
"""