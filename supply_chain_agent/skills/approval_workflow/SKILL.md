---
name: approval-workflow
description: 审批工单流程指导，当检测到 intent_level_2 = "审批工单" 时加载
triggers:
  - intent_level_2 == "审批工单"
---

# 审批工单流程

## 流程概述

```
查询工单 → 查询对应订单 → 查询对应客户统计信息
```

## 步骤详解

### Step 1: 查询工单

**目的**: 获取待审批的工单详情

**操作**:
1. 根据工单ID查询工单
2. 获取工单基本信息

**输出**: 工单详情对象

---

### Step 2: 查询对应订单

**目的**: 获取工单关联的订单信息

**前置条件**: 已完成 Step 1，获取到 order_id

**操作**:
1. 使用工单中的 order_id 查询订单详情
2. 获取订单信息

**输出**: 订单详情对象

---

### Step 3: 查询对应客户统计信息

**目的**: 获取客户的历史统计信息，辅助审批决策

**前置条件**: 已完成 Step 2，获取到 customer_id

**操作**:
1. 使用订单中的 customer_id 查询客户统计信息
2. 获取客户信息

**输出**: 客户统计信息对象

---

## 工具映射

| 步骤 | 工具名称 | 必需参数 | 输出字段 |
|------|---------|---------|---------|
| Step 1 | query_work_order | work_order_id | order_id, customer_id |
| Step 2 | query_order | order_id | customer_id, order_details |
| Step 3 | query_customer_statistics | customer_id | statistics |

## 注意事项

1. 每一步骤执行前需验证前置条件
2. 查询失败时应有重试机制
3. 所有操作需记录日志用于审计
4. 敏感信息需脱敏处理

## 渐进式披露

根据执行阶段加载对应的子流程：
- **计划生成**: 加载 `procedures/plan_generation.md`
- **参数提取**: 加载 `procedures/param_extraction.md`
- **工具执行**: 加载 `procedures/tool_execution.md`