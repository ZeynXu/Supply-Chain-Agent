# 数据库表结构文档

## 数据库概览

数据库文件：`supply_chain_agent/data/supply_chain.db`

共有 **12 个业务表**（不含 sqlite_sequence）

---

## 表结构详情

### 1. customers（客户表）

| 字段名 | 类型 | 说明 |
|--------|------|------|
| Customer_Id | INTEGER | 客户ID（主键） |
| Customer_Fname | TEXT | 客户名 |
| Customer_Lname | TEXT | 客户姓 |
| Customer_Email | TEXT | 客户邮箱 |
| Customer_Segment | TEXT | 客户细分 |
| Customer_City | TEXT | 城市 |
| Customer_Country | TEXT | 国家 |
| Customer_State | TEXT | 州/省 |
| Customer_Street | TEXT | 街道 |
| Customer_Zipcode | INTEGER | 邮编 |
| Latitude | REAL | 纬度 |
| Longitude | REAL | 经度 |

---

### 2. categories（产品分类表）

| 字段名 | 类型 | 说明 |
|--------|------|------|
| Category_Id | INTEGER | 分类ID（主键） |
| Category_Name | TEXT | 分类名称 |

---

### 3. departments（部门表）

| 字段名 | 类型 | 说明 |
|--------|------|------|
| Department_Id | INTEGER | 部门ID（主键） |
| Department_Name | TEXT | 部门名称 |

---

### 4. products（产品表）

| 字段名 | 类型 | 说明 |
|--------|------|------|
| Product_Card_Id | REAL | 产品卡片ID（主键） |
| Product_Name | TEXT | 产品名称 |
| Product_Price | TEXT | 产品价格 |
| Product_Status | TEXT | 产品状态 |
| Product_Category_Id | TEXT | 分类ID（外键） |

---

### 5. orders（订单表）

| 字段名 | 类型 | 说明 |
|--------|------|------|
| order_id | INTEGER | 订单ID（主键） |
| customer_id | TEXT | 客户ID（外键） |
| order_date | TEXT | 订单日期 |
| order_status | TEXT | 订单状态 |
| order_city | TEXT | 订单城市 |
| order_country | TEXT | 订单国家 |
| order_region | TEXT | 订单区域 |
| order_state | TEXT | 订单州/省 |
| order_zipcode | REAL | 订单邮编 |
| delivery_status | TEXT | 发货状态 |
| late_delivery_risk | INTEGER | 延迟风险标志 |
| type | TEXT | 订单类型 |
| market | TEXT | 市场 |
| benefit_per_order | REAL | 订单收益 |
| sales_per_customer | REAL | 客户累计销售额 |
| order_profit_per_order | TEXT | 订单利润 |

---

### 6. order_items（订单明细表）

| 字段名 | 类型 | 说明 |
|--------|------|------|
| order_item_id | REAL | 订单明细ID（主键） |
| order_id | INTEGER | 订单ID（外键） |
| product_card_id | REAL | 产品ID（外键） |
| order_item_discount | REAL | 折扣金额 |
| order_item_discount_rate | REAL | 折扣率 |
| order_item_product_price | REAL | 产品单价 |
| order_item_profit_ratio | REAL | 利润率 |
| order_item_quantity | REAL | 数量 |
| sales | REAL | 销售额 |
| order_item_total | REAL | 明细总额 |
| benefit_per_order | REAL | 收益 |
| sales_per_customer | REAL | 客户累计销售额 |

---

### 7. shipping（物流表）

| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | INTEGER | 记录ID（主键） |
| order_id | INTEGER | 订单ID（外键） |
| days_for_shipping_real | INTEGER | 实际运输天数 |
| days_for_shipment_scheduled | INTEGER | 计划运输天数 |
| shipping_mode | TEXT | 运输方式 |
| shipping_date | TEXT | 发货日期 |

---

### 8. work_orders（工单表）

| 字段名 | 类型 | 说明 |
|--------|------|------|
| work_order_id | TEXT | 工单ID（主键），格式：WO-YYYYMMDD-XXX |
| order_id | TEXT | 关联订单ID |
| work_type | TEXT | 工单类型（审批/异常处理/退款/调拨/质检/其他） |
| status | TEXT | 状态（待处理/待审批/处理中/已通过/已拒绝/已关闭） |
| priority | TEXT | 优先级（高/中/低） |
| description | TEXT | 描述 |
| assigned_to | TEXT | 指派给 |
| created_by | TEXT | 创建人 |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间 |
| timeline | TEXT | 时间线（JSON格式） |

---

### 9. issues（问题/异常表）

| 字段名 | 类型 | 说明 |
|--------|------|------|
| issue_id | TEXT | 问题ID（主键），格式：ISS-YYYYMMDD-XXX |
| issue_type | TEXT | 问题类型（物流延迟/库存异常/质量缺陷/数据错误/客户投诉/其他） |
| description | TEXT | 描述 |
| urgency | TEXT | 紧急程度（高/中/低） |
| affected_order | TEXT | 受影响订单 |
| reported_by | TEXT | 报告人 |
| status | TEXT | 状态（待处理/处理中/已解决/已关闭） |
| assigned_to | TEXT | 指派给 |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间 |
| updates | TEXT | 更新记录（JSON格式） |

---

### 10. entity_mappings（实体映射表）

| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | INTEGER | 记录ID（主键，自增） |
| standard_name | TEXT | 标准实体名 |
| alias | TEXT | 别名（口语化表达） |
| description | TEXT | 说明 |

---

### 11. fallback_templates（回退模板表）

| 字段名 | 类型 | 说明 |
|--------|------|------|
| error_code | TEXT | 错误编码（主键） |
| error_name | TEXT | 错误名称 |
| scenario | TEXT | 场景描述 |
| severity | TEXT | 严重等级 |
| template | TEXT | 回复模板 |
| notes | TEXT | 备注 |

---

### 12. agent_config（Agent配置表）

| 字段名 | 类型 | 说明 |
|--------|------|------|
| config_key | TEXT | 配置键（主键） |
| config_value | TEXT | 配置值（JSON格式） |
| updated_at | DATETIME | 更新时间 |

---

## 表关系图

```
customers ──┐
            │
            ├──< orders >──┬──< order_items >── products
            │              │
            │              └──< shipping
            │
            └──< work_orders
            │
            └──< issues

products ────< categories

entity_mappings (独立配置表)
fallback_templates (独立配置表)
agent_config (独立配置表)
```

---

## 枚举值定义

### work_orders.work_type（工单类型）
- 审批
- 异常处理
- 退款
- 调拨
- 质检
- 其他

### work_orders.status（工单状态）
- 待处理
- 待审批
- 处理中
- 已通过
- 已拒绝
- 已关闭

### work_orders.priority（优先级）
- 高
- 中
- 低

### issues.issue_type（问题类型）
- 物流延迟
- 库存异常
- 质量缺陷
- 数据错误
- 客户投诉
- 其他

### issues.urgency（紧急程度）
- 高
- 中
- 低
