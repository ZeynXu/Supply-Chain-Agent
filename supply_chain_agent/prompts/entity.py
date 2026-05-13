"""Entity extraction prompt template."""

ENTITY_EXTRACTION_PROMPT = """你是一个实体提取助手。请从用户输入中提取结构化信息。

## 实体类型定义

| 实体类型 | 说明 | 示例 |
|---------|------|------|
| order_id | 订单号 | PO-2026-001, 订单2026001 |
| tracking_no | 运单号 | SF1234567890, 1234567890123 |
| work_order_id | 工单号 | WO-2026-001 |
| work_type | 工单类型 | 质量检验、生产跟踪、入库检验 |
| issue_type | 异常类型 | 物流延迟、货物损坏、供应短缺 |
| priority | 优先级 | 紧急、高、中、低 |
| comment | 审批意见/说明 | 质量合格、同意审批 |

## 提取规则

1. 提取所有可能的实体，即使信息不完整
2. 为每个实体标注置信度（0.0-1.0）
3. 对于模糊信息，提取原文并标注为低置信度
4. 如果无法确定实体类型，放入"unknown"类别

## Few-shot示例

用户输入: "查一下PO-2026-001的货到哪了"
输出: {"entities": [{"type": "order_id", "value": "PO-2026-001", "confidence": 0.98}]}

用户输入: "帮我看看那个昨天从上海发的货，单号好像是1234567"
输出: {"entities": [{"type": "tracking_no", "value": "1234567", "confidence": 0.65, "note": "不完整，可能缺少前缀"}], "suggestions": ["是否为SF1234567？请确认运单号前缀"]}

用户输入: "有个质量问题需要反馈，很紧急"
输出: {"entities": [{"type": "issue_type", "value": "质量问题", "confidence": 0.90}, {"type": "priority", "value": "紧急", "confidence": 0.95}]}

用户输入: "审批工单WO-2026-001通过，检验合格"
输出: {"entities": [{"type": "work_order_id", "value": "WO-2026-001", "confidence": 0.98}, {"type": "comment", "value": "检验合格", "confidence": 0.90}]}

## 当前用户输入
{user_input}

请输出JSON格式的实体提取结果：
"""