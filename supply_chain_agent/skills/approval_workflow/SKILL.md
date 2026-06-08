---
name: approval-workflow
description: 审批工单流程指导，当检测到 intent_level_2 = "审批工单" 时加载
triggers:
  - intent_level_2 == "审批工单"
---

# 审批工单流程

## 执行流程

```
query_work_order → query_order → query_customer_statistics → approve_work_order
```

**数据依赖链**: work_order_id → order_id → customer_id

## 工具定义

| 工具 | 必需参数 | 来源 |
|-----|---------|------|
| query_work_order | work_order_id | 用户输入 |
| query_order | order_id | 上一步结果 |
| query_customer_statistics | customer_id | 上一步结果 |
| approve_work_order | work_order_id, action, comment? | 累积槽位 |

## 参数提取规则

```
query_work_order结果 → 提取 order_id, customer_id
query_order结果 → 提取 customer_id
```

**优先级**: 工具结果 > 已有槽位 > 用户输入

## 执行模式

链式执行：每完成一步，LLM解析结果并提取下一步参数。

## 错误处理

- 工具失败：终止流程，返回错误
- 参数缺失：尝试其他来源，失败则终止
- 临时错误：最多重试3次

## 注意事项

- 执行前验证前置条件
- 敏感信息脱敏
- 记录审计日志
