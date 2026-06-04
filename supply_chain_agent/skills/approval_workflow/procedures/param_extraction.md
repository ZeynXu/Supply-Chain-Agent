# 参数提取流程

## 任务

根据当前工具执行结果，为下一个工具提取或生成所需参数。

## 参数提取规则

### 从工单查询结果提取

```json
{
  "order_id": "result.order_id",
  "customer_id": "result.customer_id"
}
```

### 从订单查询结果提取

```json
{
  "customer_id": "result.customer_id"
}
```

### 参数优先级

1. **从执行结果提取**: 优先从当前工具执行结果中提取
2. **从已有槽位获取**: 如果结果中没有，从已有槽位中获取
3. **从用户输入获取**: 从用户原始输入中提取的实体

## 工具参数定义

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

## 示例

**当前工具**: query_work_order
**执行结果**: {"work_order_id": "WO-0001", "order_id": "ORD-123", "customer_id": "CUST-456", ...}
**下一个工具**: query_order
**提取参数**: {"order_id": "ORD-123"}