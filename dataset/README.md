# Dataset 数据目录说明

本目录包含智能供应链工单处理 Agent 系统的所有数据源文件。

---

## 目录结构

```
dataset/
├── BusinessData/          # 业务数据目录
├── SOPData/               # SOP 文档目录
├── OtherData/             # 其他配置数据目录
└── README.md              # 本文件
```

---

## 目录说明

### 1. BusinessData - 业务数据

业务相关的数据文件，包含供应链运营的核心业务数据。

| 文件 | 说明 |
|------|------|
| `BusinessData/DataCoSupplyChainDataset.csv` | 供应链业务数据集，包含订单、客户、产品、物流等信息 |
| `BusinessData/DescriptionDataCoSupplyChain.csv` | 业务数据字段描述文档 |

**数据内容**：
- 客户信息（3,486 条）
- 订单信息（3,861 条）
- 订单明细（5,000 条）
- 产品信息（94 条）
- 物流信息（5,000 条）

### 2. SOPData - 标准操作流程文档

供应链审批相关的 SOP（标准操作流程）管理文件。

| 文件 | 说明 |
|------|------|
| `SOPData/Supply Chain Business Approval Management Measures.md` | 供应链业务审批管理办法 |
| `SOPData/Customer Classification and Performance Quota Management Measures.md` | 客商分级与履约额度管理办法 |

**用途**：
- 加载到向量存储（ChromaDB）供语义检索
- 为 Agent 提供业务流程参考
- 支持智能问答和流程指导

### 3. OtherData - 配置数据

系统运行所需的配置文件和映射表。

| 文件 | 说明 |
|------|------|
| `OtherData/EntityMapping.csv` | 实体同义词映射表，将用户口语化表达映射到标准实体名 |
| `OtherData/FallbackResponseTemplate.csv` | 降级响应模板，当系统无法处理时的默认响应 |
| `OtherData/config.yaml` | Agent 运行配置，包含各类运行参数 |

**配置内容**：

**EntityMapping.csv**：
- 支持中文别名匹配
- 示例：`订单号` → `order_id`，`客户名` → `customer_name`

**FallbackResponseTemplate.csv**：
- 按错误码分类的响应模板
- 支持变量替换

**config.yaml**：
- 意图识别阈值
- 工具调用超时设置
- 熔断器配置
- 记忆系统参数

---

## 数据加载

系统启动时会自动从本目录加载数据：

1. **业务数据** → SQLite 数据库 (`supply_chain_agent/data/supply_chain.db`)
2. **SOP 文档** → ChromaDB 向量存储 (`supply_chain_agent/data/vector_store/`)
3. **实体映射** → SQLite 数据库 (`entity_mappings` 表)
4. **降级模板** → SQLite 数据库 (`fallback_templates` 表)
5. **Agent 配置** → SQLite 数据库 (`agent_config` 表)

**手动初始化命令**：

```bash
python -m supply_chain_agent.data.init_data
```

---

## 注意事项

1. **禁止修改文件名**：文件名已与代码硬编码关联，修改会导致加载失败
2. **编码格式**：CSV 文件使用 UTF-8 或 GBK 编码
3. **SOP 格式**：仅支持 Markdown (`.md`) 格式
4. **数据更新**：修改数据后需重新运行初始化脚本
