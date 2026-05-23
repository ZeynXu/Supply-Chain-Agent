# MCP Server 详细设计文档

## 1. 设计目标

本 MCP Server 为智能供应链工单处理 Agent 系统提供统一、安全的工具接口，封装对企业内部供应链业务数据的查询能力。所有工具均为只读操作，旨在为 Agent 的规划、执行与审计环节提供数据支撑。

**核心原则**：
- **数据真实**：所有返回数据均来源于业务数据库（MySQL）已有字段，不包含任何模拟或虚构数据。
- **边界清晰**：每个工具职责单一，功能互不重叠，覆盖 Agent 所需的全部查询场景。
- **输出标准化**：返回结构化 JSON，字段命名与数据模型一致，降低 Agent 理解成本。
- **计算透明**：对于聚合统计或状态描述，通过数据库查询与确定性的业务规则生成，逻辑可解释。

## 2. MCP Server 概述

- **协议**：MCP (Model Context Protocol)，基于 JSON-RPC 2.0。
- **传输方式**：支持 `stdio` 和 `SSE`，根据部署环境灵活切换。
- **实现语言**：Python 3.11+，使用 `fastmcp` 库快速构建。
- **数据源**：MySQL 数据库（业务数据），仅执行 SELECT 查询。

## 3. 工具清单

| 工具名称 | 功能摘要 |
|:---|:---|
| `query_customer` | 根据客户ID查询客户基本信息 |
| `query_customer_orders` | 查询某客户的订单列表（分页） |
| `query_order` | 根据订单ID查询订单头详细信息 |
| `query_order_items` | 根据订单ID查询订单行项目明细 |
| `query_product` | 根据产品卡片ID查询产品信息 |
| `query_shipment` | 根据订单ID查询物流基本信息及状态描述 |
| `query_customer_statistics` | 获取客户的风险评估统计指标及当前履约占用 |
| `create_work_order` | 创建新工单（写入操作） |
| `approve_work_order` | 审批工单（写入操作） |
| `report_issue` | 上报问题/异常（写入操作） |

## 4. 工具详细设计

### 4.1 query_customer

- **功能**：根据客户ID查询客户基本信息。
- **输入** (JSON Schema)：
  ```json
  {
    "customer_id": {
      "type": "integer",
      "description": "客户唯一标识"
    }
  }
  ```
- **输出** (JSON)：
  ```json
  {
    "customer_id": 20755,
    "first_name": "Cally",
    "last_name": "Holloway",
    "email": "c***@example.com",
    "segment": "Consumer",
    "city": "Caguas",
    "state": "PR",
    "zipcode": "725",
    "country": "Puerto Rico",
    "latitude": 18.2514534,
    "longitude": -66.03705597
  }
  ```
- **数据来源**：`customers` 表，`email` 字段已脱敏存储，直接返回。
- **异常**：`customer_id` 不存在时返回标准 MCP 404 错误。

### 4.2 query_customer_orders

- **功能**：查询某客户的所有订单概要，支持分页，默认返回最近 20 条（按 `order_date` 降序）。
- **输入**：
  ```json
  {
    "customer_id": { "type": "integer" },
    "limit": { "type": "integer", "default": 20, "minimum": 1, "maximum": 100 },
    "offset": { "type": "integer", "default": 0, "minimum": 0 }
  }
  ```
- **输出**：
  ```json
  {
    "customer_id": 20755,
    "total_orders": 45,
    "orders": [
      {
        "order_id": 77202,
        "order_date": "2018-01-31 22:56:00",
        "order_status": "COMPLETE",
        "delivery_status": "Advance shipping",
        "benefit_per_order": 91.25,
        "market": "Pacific Asia"
      }
    ]
  }
  ```
- **说明**：列表中每笔订单包含 `benefit_per_order` 作为金额参考，如需精确金额可进一步调用 `query_order` 和 `query_order_items`。
- **数据来源**：`orders` 表。

### 4.3 query_order

- **功能**：根据订单ID查询订单头详细信息。
- **输入**：`{ "order_id": { "type": "integer" } }`
- **输出**：
  ```json
  {
    "order_id": 77202,
    "customer_id": 20755,
    "order_date": "2018-01-31 22:56:00",
    "order_status": "COMPLETE",
    "delivery_status": "Advance shipping",
    "market": "Pacific Asia",
    "order_region": "Southeast Asia",
    "order_city": "Bekasi",
    "order_state": "Java Occidental",
    "order_country": "Indonesia",
    "type": "DEBIT",
    "sales_per_customer": 314.64,
    "benefit_per_order": 91.25,
    "order_profit_per_order": 91.25
  }
  ```
- **数据来源**：`orders` 表。

### 4.4 query_order_items

- **功能**：查询指定订单的所有明细行。
- **输入**：`{ "order_id": { "type": "integer" } }`
- **输出**：
  ```json
  {
    "order_id": 77202,
    "items": [
      {
        "order_item_id": 180517,
        "product_card_id": 1360,
        "quantity": 1,
        "product_price": 327.75,
        "discount": 13.11,
        "discount_rate": 0.04,
        "order_item_total": 314.64,
        "profit_ratio": 0.29,
        "sales": 327.75
      }
    ]
  }
  ```
- **数据来源**：`order_items` 表。

### 4.5 query_product

- **功能**：根据产品卡片ID查询产品详情。
- **输入**：`{ "product_card_id": { "type": "integer" } }`
- **输出**：
  ```json
  {
    "product_card_id": 1360,
    "product_category_id": 73,
    "category_name": "Sporting Goods",
    "product_name": "Smart watch",
    "product_description": "...",
    "price": 327.75,
    "product_status": 0,
    "department_id": 2,
    "department_name": "Fitness"
  }
  ```
- **数据来源**：`products` 表。

### 4.6 query_shipment

- **功能**：查询订单的物流基本信息，并根据已有字段生成确定性的状态描述。
- **输入**：`{ "order_id": { "type": "integer" } }`
- **输出**：
  ```json
  {
    "order_id": 77202,
    "shipping_mode": "Standard Class",
    "shipping_date": "2018-02-03 22:56:00",
    "days_for_shipping_real": 3,
    "days_for_shipment_scheduled": 4,
    "late_delivery_risk": 0,
    "status_description": "已于2018-02-03发货，实际运输3天，无延迟风险。"
  }
  ```
- **status_description 生成规则**：
  - 若 `shipping_date` 为 NULL：`status_description = "尚未发货。"`
  - 否则，根据 `days_for_shipping_real` 与 `days_for_shipment_scheduled` 的比较：
    - 若有 `late_delivery_risk=1` 或 `delivery_status='Late delivery'`：`"已于{shipping_date}发货，实际运输{real}天（计划{scheduled}天），存在延迟。"`
    - 否则：`"已于{shipping_date}发货，实际运输{real}天，无延迟风险。"`
  - 若 `delivery_status='Shipping canceled'`：`status_description` 追加 `" 该订单物流已取消。"`
- **数据来源**：`shipments` 表，订单的 `delivery_status` 可通过关联 `orders` 表获取。此工具会执行 JOIN 查询。

### 4.7 query_customer_statistics

- **功能**：为客户风险评估和审批决策提供聚合统计指标，包括历史交易行为及当前履约占用，全部基于已有数据计算。
- **输入**：`{ "customer_id": { "type": "integer" } }`
- **输出**：
  ```json
  {
    "customer_id": 20755,
    "total_sales": 12850.50,
    "total_orders": 15,
    "delayed_orders": 2,
    "cancelled_orders": 0,
    "avg_order_profit": 85.20,
    "late_delivery_rate": 0.133,
    "current_occupied_amount": 1200.00,
    "current_pending_orders": 1
  }
  ```
- **指标计算口径**（全部通过 SQL 聚合实现）：
  - `total_sales`：该客户所有订单中最大的 `sales_per_customer` 值（因其为累计值，取最后一条订单的累计销售额即可反映总消费）。
  - `total_orders`：`orders` 表该客户的总订单数。
  - `delayed_orders`：`shipments` 表中关联后 `late_delivery_risk=1` 的订单数。
  - `cancelled_orders`：`orders` 表中 `delivery_status='Shipping canceled'` 的订单数。
  - `avg_order_profit`：`orders` 表中 `order_profit_per_order` 的平均值。
  - `late_delivery_rate`：`delayed_orders / total_orders`，若 `total_orders=0` 则为 0。
  - `current_occupied_amount`：当前未完成订单（`order_status IN ('PENDING','PROCESSING','PENDING_PAYMENT','PAYMENT_REVIEW','ON_HOLD')`）对应的 `order_items.order_item_total` 汇总值。
  - `current_pending_orders`：上述未完成订单的数量。
- **数据来源**：`orders`、`order_items`、`shipments` 表联合查询。

### 4.8 create_work_order

- **功能**：创建新工单，用于记录需要人工介入或系统处理的业务事项。
- **输入**：
  ```json
  {
    "work_type": {
      "type": "string",
      "description": "工单类型，如：审批、异常处理、退款、调拨等",
      "enum": ["审批", "异常处理", "退款", "调拨", "质检", "其他"]
    },
    "description": {
      "type": "string",
      "description": "工单描述，详细说明需要处理的事项"
    },
    "order_id": {
      "type": "string",
      "description": "关联订单ID（可选）"
    },
    "priority": {
      "type": "string",
      "description": "优先级",
      "enum": ["高", "中", "低"],
      "default": "中"
    },
    "assigned_to": {
      "type": "string",
      "description": "分配给谁处理（可选，不指定则由系统自动分配）"
    }
  }
  ```
- **输出**：
  ```json
  {
    "success": true,
    "work_order": {
      "work_order_id": "WO-20240523-001",
      "order_id": "77202",
      "work_type": "异常处理",
      "status": "待处理",
      "priority": "高",
      "description": "订单物流延迟超过7天，需人工跟进",
      "assigned_to": "异常处理组",
      "created_by": "Agent System",
      "created_at": "2024-05-23 14:30:00",
      "timeline": [
        {
          "timestamp": "2024-05-23 14:30:00",
          "actor": "Agent System",
          "action": "创建工单"
        }
      ]
    }
  }
  ```
- **业务规则**：
  - `work_order_id` 自动生成，格式：`WO-{YYYYMMDD}-{序号}`，序号按当天工单数递增。
  - 若未指定 `assigned_to`，根据 `work_type` 自动分配：
    - "审批" → "审批组"
    - "异常处理" → "异常处理组"
    - "退款" → "财务组"
    - "调拨" → "仓储组"
    - "质检" → "质检组"
    - "其他" → "综合事务组"
  - `status` 初始为 "待处理"。
  - `timeline` 记录工单全生命周期事件。
- **数据写入**：`work_orders` 表 INSERT 操作。

### 4.9 approve_work_order

- **功能**：审批工单，更新工单状态并记录审批意见。
- **输入**：
  ```json
  {
    "work_order_id": {
      "type": "string",
      "description": "工单唯一标识"
    },
    "action": {
      "type": "string",
      "description": "审批动作",
      "enum": ["approve", "reject", "escalate"]
    },
    "comment": {
      "type": "string",
      "description": "审批意见/备注"
    },
    "approver": {
      "type": "string",
      "description": "审批人标识（可选，默认为当前操作用户）"
    }
  }
  ```
- **输出**：
  ```json
  {
    "success": true,
    "work_order": {
      "work_order_id": "WO-20240523-001",
      "status": "已通过",
      "updated_at": "2024-05-23 15:00:00",
      "timeline": [
        {
          "timestamp": "2024-05-23 14:30:00",
          "actor": "Agent System",
          "action": "创建工单"
        },
        {
          "timestamp": "2024-05-23 15:00:00",
          "actor": "张三",
          "action": "审批通过",
          "comment": "已核实情况，同意处理"
        }
      ]
    }
  }
  ```
- **业务规则**：
  - `action` 对应状态变更：
    - "approve" → `status` = "已通过"
    - "reject" → `status` = "已拒绝"
    - "escalate" → `status` = "待审批"（升级审批）
  - 仅 `status` 为 "待处理" 或 "待审批" 的工单可执行审批操作。
  - 每次操作自动追加 `timeline` 事件记录。
- **数据写入**：`work_orders` 表 UPDATE 操作。

### 4.10 report_issue

- **功能**：上报问题/异常，用于记录供应链过程中发现的各类问题。
- **输入**：
  ```json
  {
    "issue_type": {
      "type": "string",
      "description": "问题类型",
      "enum": ["物流延迟", "库存异常", "质量缺陷", "数据错误", "客户投诉", "其他"]
    },
    "description": {
      "type": "string",
      "description": "问题描述，详细说明问题详情"
    },
    "affected_order": {
      "type": "string",
      "description": "受影响订单ID（可选）"
    },
    "urgency": {
      "type": "string",
      "description": "紧急程度",
      "enum": ["高", "中", "低"],
      "default": "中"
    },
    "reported_by": {
      "type": "string",
      "description": "报告人标识（可选，默认为Agent System）"
    }
  }
  ```
- **输出**：
  ```json
  {
    "success": true,
    "issue": {
      "issue_id": "ISS-20240523-001",
      "issue_type": "物流延迟",
      "description": "订单77202物流已超期5天未送达",
      "urgency": "高",
      "affected_order": "77202",
      "reported_by": "Agent System",
      "status": "待处理",
      "assigned_to": "异常处理组",
      "created_at": "2024-05-23 14:35:00",
      "updates": [
        {
          "timestamp": "2024-05-23 14:35:00",
          "user": "Agent System",
          "action": "创建问题报告",
          "details": "自动创建物流延迟问题报告"
        }
      ]
    }
  }
  ```
- **业务规则**：
  - `issue_id` 自动生成，格式：`ISS-{YYYYMMDD}-{序号}`，序号按当天问题数递增。
  - `status` 初始为 "待处理"。
  - `assigned_to` 默认为 "异常处理组"，可根据 `issue_type` 配置自动分配。
  - 若指定了 `affected_order`，系统会自动关联订单信息。
- **数据写入**：`issues` 表 INSERT 操作。

## 5. 工具分类

根据操作类型，工具分为两大类：

### 5.1 只读查询工具（Read-Only）
- `query_customer`
- `query_customer_orders`
- `query_order`
- `query_order_items`
- `query_product`
- `query_shipment`
- `query_customer_statistics`

### 5.2 写入操作工具（Write Operations）
- `create_work_order` - 创建工单
- `approve_work_order` - 审批工单
- `report_issue` - 上报问题

**注意**：写入操作工具需要额外的权限控制和事务管理，确保数据一致性。

## 6. 错误处理

所有工具遵循 MCP 标准错误响应格式，包含 `code` 和 `message`。常见错误码：

| 错误码 | 含义 |
|:---|:---|
| 404 | 请求的资源（如订单、客户、工单）不存在 |
| 502 | 数据库连接失败或查询超时 |
| 422 | 输入参数校验失败（如类型错误、必填缺失） |
| 500 | 服务器内部错误（如查询执行异常） |
| 409 | 业务冲突（如工单状态不允许当前操作） |
| 403 | 权限不足（如无权审批该工单） |

Agent 审计员在捕获这些错误后，将依据降级响应模板生成用户提示。

## 7. 工具边界与无冗余保证

- `query_customer` 提供静态客户属性；`query_customer_statistics` 提供动态统计与风险指标，职责互补。
- `query_order` 返回订单头完整信息；`query_order_items` 返回明细行；`query_customer_orders` 返回分页列表概要，三者粒度不同，互不重叠。
- `query_shipment` 聚焦物流计划与实际执行信息，并给出格式化状态描述，无轨迹模拟需求。
- 所有工具均严格对应数据模型中的实体，无交叉返回相同字段集合的情况。

## 8. 工具调用场景举例

**场景：用户查询“订单 77202 的物流状态”**
1. 执行Agent调用 `query_order(77202)` 获取订单状态和发货状态。
2. 调用 `query_shipment(77202)` 获取运输模式、日期、延迟风险及状态描述。
3. 无需额外工具，综合回复。

**场景：用户申请”审批客户 20755 的新订单”**
1. 调用 `query_customer(20755)` 了解客户基本信息。
2. 调用 `query_customer_statistics(20755)` 获取风险指标与当前履约占用。
3. 结合《客商分级与履约额度管理办法》知识库，审计员Agent输出审批建议。如需订单详情，可进一步调用 `query_order`。

**场景：用户查询”订单 77202 物流延迟，帮我处理”**
1. 调用 `query_order(77202)` 和 `query_shipment(77202)` 确认物流状态。
2. 若确认存在延迟问题，调用 `create_work_order` 创建异常处理工单。
3. 同时调用 `report_issue` 上报问题，建立问题追踪记录。

**场景：管理人员”审批工单 WO-20240523-001”**
1. 调用 `approve_work_order(work_order_id=”WO-20240523-001”, action=”approve”, comment=”已核实，同意处理”)`。
2. 系统更新工单状态并记录审批历史。

## 9. 实现注意事项

- 所有查询均使用数据库只读账号，避免误操作。
- 对 `order_id`、`customer_id` 等高频查询列已建立索引，确保性能。
- `query_customer_statistics` 涉及聚合计算，可考虑对近期数据设置缓存（由 Redis 负责），但数据本体仍源自数据库。
- 状态描述生成逻辑集中在 query_shipment 内部，方便统一调整话术。
- **写入操作工具**（create_work_order、approve_work_order、report_issue）需要：
  - 使用数据库事务确保数据一致性。
  - 实现幂等性设计，避免重复创建。
  - 记录完整的操作审计日志。
  - 工单ID和问题ID生成需要考虑并发安全，建议使用数据库序列或分布式ID生成器。