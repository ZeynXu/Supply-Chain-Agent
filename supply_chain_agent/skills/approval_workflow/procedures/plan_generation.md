# 执行计划生成流程

## 任务

根据用户请求和提取的实体，生成审批工单的执行计划。

## 输入

- 用户请求信息
- 提取的实体（work_order_id, action 等）

## 输出

JSON 格式的执行计划：

```json
{
  "tasks": [
    {"name": "查询工单", "tool": "query_work_order", "description": "获取工单详情"},
    {"name": "查询订单", "tool": "query_order", "description": "获取关联订单信息"},
    {"name": "查询客户统计", "tool": "query_customer_statistics", "description": "获取客户统计信息"}
  ]
}
```

## 执行计划生成规则

1. **标准流程**: 按顺序执行 query_work_order → query_order → query_customer_statistics
2. **前置条件检查**: 确保每一步的必需参数可以从上一步结果中获取
3. **数据依赖**:
   - query_order 需要 order_id（从 query_work_order 结果获取）
   - query_customer_statistics 需要 customer_id（从 query_order 结果获取）

## 示例

**用户输入**: "审批工单 WO-0001 通过"

**提取实体**: {"work_order_id": "WO-0001", "action": "approve"}

**生成计划**:
```json
{
  "tasks": [
    {"name": "查询工单", "tool": "query_work_order", "description": "获取工单 WO-0001 详情"},
    {"name": "查询订单", "tool": "query_order", "description": "获取关联订单信息"},
    {"name": "查询客户统计", "tool": "query_customer_statistics", "description": "获取客户统计信息辅助决策"}
  ]
}
```