# 工具执行指导

## 执行模式

审批工单流程使用**链式执行模式**：
- 依次执行每个工具
- 每执行完一个工具，将结果发送给 LLM 解析
- LLM 输出下一步工具的入参
- 继续执行直到所有工具执行完毕

## 执行流程

```
1. 执行 query_work_order(work_order_id)
   ↓
2. LLM 解析结果，提取 order_id
   ↓
3. 执行 query_order(order_id)
   ↓
4. LLM 解析结果，提取 customer_id
   ↓
5. 执行 query_customer_statistics(customer_id)
   ↓
6. 返回所有执行结果
```

## 错误处理

1. **工具执行失败**: 记录错误，终止流程，返回错误信息
2. **参数验证失败**: 尝试从其他来源获取参数，如果仍失败则终止
3. **重试机制**: 对于临时性错误，最多重试 3 次

## 执行结果结构

```json
{
  "success": true,
  "results": {
    "query_work_order": {...},
    "query_order": {...},
    "query_customer_statistics": {...}
  },
  "final_slots": {
    "work_order_id": "WO-0001",
    "order_id": "ORD-123",
    "customer_id": "CUST-456"
  }
}
```