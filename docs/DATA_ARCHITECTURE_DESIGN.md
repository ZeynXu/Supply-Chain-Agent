### **智能供应链工单处理Agent系统 - 数据架构规范设计**

### 1. 设计目标与原则

#### 1.1 数据架构承载的核心场景

1. **实时工单处理**：Agent 通过 MCP 工具查询供应链订单状态、物流轨迹、客户与产品信息，要求低延迟、强一致性的业务数据查询。
2. **智能决策增强**：Agent 检索标准操作流程(SOP)、审批规范文档（含合同条款参考）等企业内部知识，辅助规划与审计，要求语义相似度检索能力。
3. **高可用降级**：当外部依赖不可用时，Agent 需依靠缓存数据或静态规则优雅降级，避免服务中断。

#### 1.2 设计原则

- **业务数据模型严格对齐**：以提供的供应链数据集字段说明为准绳，不做任何超出原始字段的表结构设计。对于原始数据中不存在的字段，若需在 Mock 层动态生成，则仅存在于接口响应中，不进行持久化建表。
- **记忆数据向量化**：将非结构化知识文档转化为向量并建立索引，实现语义级快速召回。
- **降级策略配置化**：降级行为通过配置中心动态下发，与业务代码解耦。
- **敏感字段最小化**：客户密码、邮箱等敏感字段仅做脱敏存储或处理，Agent 输出时绝不暴露原文。

---

### 2. 数据分层架构总览

```
┌─────────────────────────────────────────────────────────────┐
│                     应用层 (Agent 工作流)                     │
└───┬──────────┬──────────┬──────────┬──────────┬─────────────┘
    │          │          │          │          │
    ▼          ▼          ▼          ▼          ▼
┌───────┐ ┌───────┐ ┌───────┐ ┌───────┐ ┌───────┐
│ 业务   │ │ 知识   │ │ 缓存   │ │ 配置   │ │ 事件   │
│ 数据库 │ │ 向量库 │ │ 数据库 │ │ 中心   │ │ 日志库 │
│(MySQL)│ │(Milvus)│ │(Redis)│ │(K8s CM)│ │(ES)   │
└───────┘ └───────┘ └───────┘ └───────┘ └───────┘
 实时查询   语义检索   降级/加速   动态规则   可观测性
```

- **业务数据库 (MySQL)**：模拟企业内部 ERP 系统，严格依据原始字段说明存储订单、产品、客户、物流等核心实体。
- **知识向量库 (Milvus)**：长期记忆载体，存储 SOP 手册、审批规范文档（含合同条款参考）等非结构化知识，供 Agent 通过 RAG 检索。
- **缓存数据库 (Redis)**：加速高频查询，存储降级时的缓存数据，以及会话级临时状态。
- **配置中心 (Kubernetes ConfigMap)**：管理 Agent 行为参数，如熔断阈值、重试次数等，支持热更新。
- **事件日志库 (Elasticsearch)**：集中存储结构化日志与链路追踪 Span，用于系统可观测与事后审计。

---

### 3. 核心业务数据模型

本节严格依据所提供的供应链数据字段进行规范化设计。共拆分为 **客户、产品、订单、订单明细、物流** 五个核心实体，一个数据项对应一个字段，无额外添加。

#### 3.1 实体关系图

```
┌──────────┐       ┌──────────────┐       ┌──────────┐
│ Customer │1    * │    Order     │1    * │ OrderItem│
└──────────┘       └──────────────┘       └──────────┘
     │                   │                        │
     │                   │                        │
     ▼                   ▼                        ▼
┌──────────┐       ┌──────────────┐       ┌──────────┐
│  (地址    │       │  Shipment   │       │ Product  │
│   属性)   │       └──────────────┘       └──────────┘
└──────────┘
```
*注：地址信息作为客户和订单实体的内嵌属性存在，不单独建表。*

#### 3.2 表结构定义

##### 3.2.1 客户表 (customers)

严格依据原始字段 `Customer Id, Customer Fname, Customer Lname, Customer Email, Customer Password, Customer Segment, Customer Street, Customer City, Customer State, Customer Zipcode, Customer Country, Latitude, Longitude` 建表。

| 字段名 | 数据类型 | 说明 | 对应原始字段 |
|:---|:---|:---|:---|
| customer_id | INT | 主键 | Customer Id |
| first_name | VARCHAR(100) | 客户名 | Customer Fname |
| last_name | VARCHAR(100) | 客户姓 | Customer Lname |
| email | VARCHAR(255) | 邮箱地址（存储脱敏后形式，如 `u***@domain.com`） | Customer Email |
| password_masked | VARCHAR(255) | 掩码后的客户密钥 | Customer Password |
| segment | ENUM('Consumer','Corporate','Home Office') | 客户细分 | Customer Segment |
| street | VARCHAR(255) | 客户所在街道 | Customer Street |
| city | VARCHAR(100) | 客户所在城市 | Customer City |
| state | VARCHAR(100) | 客户所在州/省 | Customer State |
| zipcode | VARCHAR(20) | 邮政编码 | Customer Zipcode |
| country | VARCHAR(100) | 客户所在国家 | Customer Country |
| latitude | DECIMAL(10,7) | 纬度 | Latitude |
| longitude | DECIMAL(10,7) | 经度 | Longitude |

**索引设计**：主键 `customer_id`；对 `email` 建唯一索引；对 `segment`、`country` 建普通索引。
**Agent 工具映射**：`query_customer(customer_id)` -> 返回客户基本信息和地址。

##### 3.2.2 产品表 (products)

严格依据原始字段 `Product Card Id, Product Category Id, Category Name, Product Name, Product Description, Product Price, Product Status, Department Id, Department Name` 建表。

| 字段名 | 数据类型 | 说明 | 对应原始字段 |
|:---|:---|:---|:---|
| product_card_id | INT | 主键 | Product Card Id |
| product_category_id | INT | 产品品类ID | Product Category Id |
| category_name | VARCHAR(200) | 品类名称 | Category Name |
| product_name | VARCHAR(300) | 产品名称 | Product Name |
| product_description | TEXT | 产品描述 | Product Description |
| price | DECIMAL(12,2) | 产品单价 | Product Price |
| product_status | TINYINT | 库存状态 (0:可用, 1:不可用) | Product Status |
| department_id | INT | 所属部门ID | Department Id |
| department_name | VARCHAR(200) | 部门名称 | Department Name |

**索引设计**：主键 `product_card_id`；对 `product_category_id` 建索引；对 `product_name` 建 FULLTEXT 索引。
**Agent 工具映射**：`query_product(product_card_id)` -> 返回产品详情与库存状态。

##### 3.2.3 订单头表 (orders)

严格依据原始字段 `Order Id, Order Customer Id, order date (DateOrders), Order Status, Delivery Status, Market, Order Region, Order City, Order State, Order Country, Sales per customer, Benefit per order, Order Profit Per Order, Type` 建表。

| 字段名 | 数据类型 | 说明 | 对应原始字段 |
|:---|:---|:---|:---|
| order_id | INT | 主键 | Order Id |
| customer_id | INT | 外键，关联客户 | Order Customer Id |
| order_date | DATETIME | 下单时间 | order date (DateOrders) |
| order_status | ENUM('COMPLETE','PENDING','CLOSED','PENDING_PAYMENT','CANCELED','PROCESSING','SUSPECTED_FRAUD','ON_HOLD','PAYMENT_REVIEW') | 订单状态 | Order Status |
| delivery_status | ENUM('Advance shipping','Late delivery','Shipping canceled','Shipping on time') | 发货状态 | Delivery Status |
| market | VARCHAR(100) | 目标市场区域 | Market |
| order_region | VARCHAR(100) | 订单区域 | Order Region |
| order_city | VARCHAR(100) | 收货城市 | Order City |
| order_state | VARCHAR(100) | 收货州/省 | Order State |
| order_country | VARCHAR(100) | 收货国家 | Order Country |
| sales_per_customer | DECIMAL(12,2) | 客户历史累计销售额 | Sales per customer |
| benefit_per_order | DECIMAL(12,2) | 本单收益 | Benefit per order |
| order_profit_per_order | DECIMAL(12,2) | 本单利润 | Order Profit Per Order |
| type | VARCHAR(50) | 交易类型 | Type |

**索引设计**：主键 `order_id`；对 `customer_id`、`order_status` 建索引。
**Agent 工具映射**：`query_order(order_id)` -> 返回订单基本信息。

##### 3.2.4 订单明细表 (order_items)

严格依据原始字段 `Order Item Id, Order Id, Order Item Cardprod Id, Order Item Quantity, Order Item Product Price, Order Item Discount, Order Item Discount Rate, Order Item Total, Order Item Profit Ratio, Sales` 建表。

| 字段名 | 数据类型 | 说明 | 对应原始字段 |
|:---|:---|:---|:---|
| order_item_id | INT | 主键 | Order Item Id |
| order_id | INT | 外键，关联订单 | Order Id |
| product_card_id | INT | 外键，关联产品 | Order Item Cardprod Id |
| quantity | INT | 购买数量 | Order Item Quantity |
| product_price | DECIMAL(12,2) | 产品原单价 | Order Item Product Price |
| discount | DECIMAL(12,2) | 折扣金额 | Order Item Discount |
| discount_rate | DECIMAL(5,4) | 折扣率 | Order Item Discount Rate |
| order_item_total | DECIMAL(12,2) | 行项目总金额 | Order Item Total |
| profit_ratio | DECIMAL(5,4) | 行项目利润率 | Order Item Profit Ratio |
| sales | DECIMAL(12,2) | 行项目销售额 | Sales |

**索引设计**：主键 `order_item_id`；对 `order_id` 建索引。
**Agent 工具映射**：`query_order_items(order_id)` -> 返回订单下所有产品明细。

##### 3.2.5 物流表 (shipments)

严格依据原始字段 `Order Id, Shipping Mode, Shipping date (DateOrders), Days for shipping (real), Days for shipment (scheduled), Late_delivery_risk` 建表。`Order Id` 作为本表主键，与订单表形成一对一关系。

| 字段名 | 数据类型 | 说明 | 对应原始字段 |
|:---|:---|:---|:---|
| order_id | INT | 主键，外键关联订单表 | Order Id |
| shipping_mode | ENUM('Standard Class','First Class','Second Class','Same Day') | 运输模式 | Shipping Mode |
| shipping_date | DATETIME | 实际发货日期 | Shipping date (DateOrders) |
| days_for_shipping_real | INT | 实际运输天数 | Days for shipping (real) |
| days_for_shipment_scheduled | INT | 计划运输天数 | Days for shipment (scheduled) |
| late_delivery_risk | TINYINT | 延迟风险标记 (0:无风险, 1:有风险) | Late_delivery_risk |

**索引设计**：主键 `order_id`；对 `shipping_date` 建索引。
**Agent 工具映射**：`query_shipment(order_id)` -> 返回物流基本信息（发货方式、日期、延迟风险等）。

---

### 4. 长期记忆数据模型 (知识向量库)

长期记忆仅保留 **SOP 文档库** 与 **实体同义词库** 两部分，为 Agent 提供规则参考和语义映射能力。

#### 4.1 标准作业程序与审批规范库 (sop_documents)

**存储目的**：存储供应链工单处理的规章制度、操作手册、审批规范（**包含合同条款参考能力，如“采购金额超过X元需附质量保证协议”等条款**），作为 Agent 规划与审计的知识依据。

- **数据来源**：从企业内部 PDF/Word/Confluence 文档中提取的条款片段。
- **分块策略**：按段落分割，每块 500~1000 tokens，相邻块保持 10% 内容重叠。
- **存储结构**：

| 字段名 | 类型 | 说明 |
|:---|:---|:---|
| doc_id | VARCHAR(36) | 主键，UUID |
| chunk_id | INT | 分块序号 |
| title | VARCHAR(255) | 来源文档标题 |
| content | TEXT | 分块后的文本内容 |
| doc_type | ENUM('sop', 'approval_policy', 'contract_clause') | 文档类型，包含合同条款类型 |
| version | INT | 版本号 |
| effective_date | DATE | 生效日期 |
| status | ENUM('active', 'archived') | 状态 |
| embedding_vector | FLOAT_VECTOR(1024) | 文本内容向量化表示 |

- **检索场景**：
  - 当执行 Agent 需要审批订单时，检索 `doc_type IN ('approval_policy', 'contract_clause')` 的文档，获取审批金额阈值、所需资质清单、合同条款约束等。
  - 当规划 Agent 识别到特定意图（如“异常处理”），检索 `doc_type = 'sop'` 的相关操作流程。

#### 4.2 实体同义词库 (entity_synonyms)

**存储目的**：辅助意图识别 Agent，将用户口语化表达映射到标准实体名。

| 字段名 | 类型 | 说明 |
|:---|:---|:---|
| synonym_id | INT | 主键，自增 |
| standard_name | VARCHAR(100) | 标准实体名 (如 `order_id`) |
| alias | VARCHAR(200) | 别名 (如“订单号”、“订单编号”、“PO单号”) |
| entity_type | VARCHAR(50) | 实体类型 (如 `identifier`) |

**存储位置**：此数据量小且稳定，可直接使用 MySQL 配置表存储，并在 Redis 中全量缓存。无需向量化。

---

### 5. 降级响应策略数据模型

#### 5.1 静态兜底模板表 (degradation_fallback)

存储预定义的降级回复模板。MySQL 存储，启动时加载至 Redis。

| 字段名 | 类型 | 说明 |
|:---|:---|:---|
| error_code | VARCHAR(50) | 错误场景编码，如 `QUERY_ORDER_TIMEOUT`, `SHIPMENT_NOT_FOUND` |
| fallback_template | TEXT | 回复模板，支持 `{order_id}` 等占位符 |
| severity | ENUM('info', 'warning', 'error') | 严重等级 |

#### 5.2 缓存键设计 (Redis)

| 键模式 | 值类型 | TTL | 说明 |
|:---|:---|:---|:---|
| `order:{order_id}` | Hash | 300s | 订单头信息缓存 |
| `shipment:{order_id}` | String (JSON) | 600s | 物流信息缓存 |
| `session:{session_id}:state` | JSON | 1800s | Agent 工作记忆外置备份 |
| `synonyms:entity` | Hash | 3600s | 实体同义词全量缓存 |

#### 5.3 配置中心数据结构 (Agent 行为参数)

```yaml
agent_config:
  intent_classifier:
    threshold: 0.75
  execution:
    max_retries: 2
    tool_call_timeout: 10s
    circuit_breaker:
      failure_threshold: 5
      recovery_timeout: 300s
  clarification:
    max_rounds: 3
  memory:
    short_term_max_tokens: 4096
    summary_trigger_tokens: 3000
  degradation:
    static_response_enabled: true
    cache_fallback_enabled: true
```

---

### 6. 数据生命周期管理

| 数据类别 | 存储周期 | 清理策略 |
|:---|:---|:---|
| 业务数据 (MySQL) | 永久保留 | 提供数据初始化脚本，每日可重置为种子数据 |
| 向量数据 (Milvus) | 长期保留，版本化管理 | SOP 更新时新增 chunk 并标记旧版本 `archived` |
| 缓存数据 (Redis) | TTL 自动过期 | 最大 TTL 不超过 1 小时 |
| 日志数据 (ES) | 保留 30 天 | 通过 ILM 策略自动归档或删除 |

---

### 7. 数据安全与合规

- **脱敏处理**：`customers` 表的 `email` 字段仅存储脱敏后形式；`password_masked` 仅存储原始掩码值。Agent 任何输出均不包含原始密码。
- **访问控制**：为不同服务分配最小权限的数据库只读/读写账号。
- **审计日志**：Agent 产生的任何写操作建议均需记录操作人、时间、内容快照，存入 Elasticsearch 或独立审计表。

---

### 8. 技术选型总结

| 存储类型 | 选型 | 理由 |
|:---|:---|:---|
| 关系型数据库 | MySQL 8.0 | 支持全文索引，严格 Schema 适合表达规范化业务实体 |
| 向量数据库 | Milvus 2.4+ | 支持混合查询，满足知识库语义检索需求 |
| 缓存 | Redis 7.0 | 丰富数据结构，可同时用于缓存与会话状态管理 |
| 搜索引擎/日志 | Elasticsearch 8.x + Kibana | 日志聚合与可观测性分析 |
| 配置中心 | Kubernetes ConfigMap | 轻量，零额外依赖，满足现阶段需求 |