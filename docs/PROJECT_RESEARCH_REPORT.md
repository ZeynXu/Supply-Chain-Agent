# 智能供应链工单处理Agent系统 - 项目研究报告

**文档版本**: V2.8
**生成日期**: 2026年6月8日
**研究范围**: 完整项目代码与文档分析
**更新说明**: V2.8新增Agent评估系统（四层评估架构：九维轨迹评分、LLM Judge质量评分、Cohen's Kappa校准、数据集管理）  

---

## 目录

1. [项目概述](#1-项目概述)
2. [系统架构设计](#2-系统架构设计)
3. [核心模块详解](#3-核心模块详解)
4. [技术栈分析](#4-技术栈分析)
5. [工作流程机制](#5-工作流程机制)
6. [记忆系统设计](#6-记忆系统设计)
7. [MCP工具系统](#7-mcp工具系统)
8. [前端界面设计](#8-前端界面设计)
9. [评估体系与性能指标](#9-评估体系与性能指标)
10. [配置与部署](#10-配置与部署)
11. [性能指标分析](#11-性能指标分析)
12. [项目特色与创新点](#12-项目特色与创新点)
13. [代码质量分析](#13-代码质量分析)
14. [Harness Engineering 工程化能力](#14-harness-engineering-工程化能力-v27新增)
15. [Agent评估系统](#15-agent评估系统-v28新增)
16. [未来扩展建议](#16-未来扩展建议)

---

## 1. 项目概述

### 1.1 项目定位

**智能供应链工单处理Agent系统**是一个基于LangGraph框架构建的L3级自主Agent系统，为供应链运营团队提供协作副驾驶能力。

**核心定位**：
- **产品级别**: L3级自主Agent（明确规则和高置信度场景下自主执行，边缘场景主动请求人工接管）
- **服务对象**: 供应链运营专员（主要）、IT运维/系统管理员（次要）
- **核心价值**: 自动化工单处理、跨系统查询、智能意图识别、多轮对话澄清

### 1.2 核心功能模块

| 模块 | 功能描述 | 技术实现 |
|------|----------|----------|
| **意图识别** | 三级意图分类体系，支持模糊输入处理 | 规则引擎 + LLM（智谱GLM-4.7）+ BERT NER |
| **多轮信息收集** | 主动澄清缺失信息，最多3次追问 | LangGraph interrupt机制 |
| **跨系统查询** | MCP工具调用，支持熔断降级 | FastMCP + 熔断器模式 |
| **报告生成** | 多模态输出卡片，结构化响应 | ReportGenerator |
| **异常处理** | 智能重试、熔断保护、降级响应 | RetryManager + CircuitBreaker |

### 1.3 项目目录结构

```
Supply_Chain_Agent/
├── supply_chain_agent/           # 主模块
│   ├── common/                   # 公共模块
│   │   ├── exceptions.py         # 异常层次结构
│   │   ├── service_container.py  # 服务容器（依赖注入）
│   │   ├── protocols.py          # 消息协议定义
│   │   ├── param_validator.py    # 参数验证器
│   │   └── valid_values.py       # 有效值定义
│   ├── agents/                   # Agent定义
│   │   ├── orchestrator.py       # 总控Agent - 协调所有子Agent
│   │   ├── parser.py             # 解析师Agent - 意图识别与实体提取
│   │   ├── executor.py           # 调度员Agent - 工具编排与执行
│   │   ├── auditor.py            # 审计员Agent - 结果验证与风控
│   │   ├── report_generator.py   # 报告生成器 - 响应格式化
│   │   ├── retry_manager.py      # 重试管理器 - 智能重试与熔断
│   │   └── llm_client.py         # LLM客户端 - 统一LLM接口
│   ├── nlp/                      # NLP模块
│   │   ├── bert_ner.py           # BERT NER实体识别 (~330行)
│   │   └── __init__.py           # 模块初始化
│   ├── models/                   # 模型文件
│   │   └── bert-chinese-wwm/     # BERT中文预训练模型
│   │       ├── config.json       # 模型配置
│   │       ├── pytorch_model.bin # 模型权重 (~393MB)
│   │       └── vocab.txt         # 词表文件
│   ├── tools/                    # MCP工具实现
│   │   ├── server.py             # MCP服务器 - 工具服务端 (~754行)
│   │   └── client.py             # 工具客户端 - 带熔断保护 (~490行)
│   ├── graph/                    # LangGraph工作流
│   │   ├── state.py              # 全局状态定义 (~223行)
│   │   ├── workflow.py           # 节点与边逻辑 (~949行)
│   │   └── visualizer.py         # 工作流可视化
│   ├── memory/                   # 记忆系统
│   │   ├── vector_store.py       # 向量存储管理 (~666行)
│   │   ├── checkpoint.py         # 检查点管理
│   │   └── knowledge_retriever.py# 知识检索器
│   ├── prompts/                  # Prompt模板
│   │   ├── intent.py             # 意图识别Prompt
│   │   ├── entity.py             # 实体提取Prompt
│   │   ├── fallback.py           # 降级响应Prompt
│   │   ├── fallback_templates.py # 降级响应模板
│   │   ├── execution_plan.py     # 执行计划Prompt
│   │   └── combined.py           # 组合Prompt
│   ├── monitoring/               # 监控系统
│   │   └── stability_monitor.py  # 稳定性监控
│   ├── harness/                  # Harness Engineering工程化模块 (V2.7新增)
│   │   ├── __init__.py           # 模块初始化
│   │   ├── config.py             # Harness配置管理
│   │   ├── decorators.py         # 参数预检装饰器
│   │   ├── rules/                # Layer 1: 业务规则
│   │   │   ├── __init__.py
│   │   │   ├── loader.py         # YAML规则加载器
│   │   │   ├── evaluator.py      # 规则评估引擎
│   │   │   └── business_rules.yaml # 业务规则配置
│   │   ├── observability/        # Layer 2: 可观测性
│   │   │   ├── __init__.py
│   │   │   ├── metrics.py        # Prometheus指标
│   │   │   ├── logging_config.py # 结构化日志
│   │   │   ├── trace.py          # Trace收集器
│   │   │   └── trace_cli.py      # Trace查询工具
│   │   ├── evals/                # Layer 2: Evals评估
│   │   │   ├── __init__.py
│   │   │   ├── base.py           # 基础评估器
│   │   │   ├── intent_eval.py    # 意图评估器
│   │   │   ├── tool_eval.py      # 工具评估器
│   │   │   ├── audit_eval.py     # 审计评估器
│   │   │   └── e2e_eval.py       # 端到端评估器
│   │   ├── feedback/             # Layer 3: 反馈改进
│   │   │   ├── __init__.py
│   │   │   ├── cluster_errors.py # 错误聚类脚本
│   │   │   └── weekly_report.py  # 周度报告生成
│   │   ├── spec/                 # SPEC规范文件
│   │   │   ├── intent_schema.json
│   │   │   └── tool_params_schema.json
│   │   └── playbook.md           # Harness运维手册
│   ├── evaluation/               # Agent评估系统 (V2.8新增)
│   │   ├── __init__.py           # 模块初始化
│   │   ├── trajectory_scorer.py  # 九维轨迹评分
│   │   ├── quality_scorer.py     # LLM Judge质量评分
│   │   ├── kappa_calibration.py  # Cohen's Kappa校准
│   │   ├── harness_integration.py # Harness集成
│   │   ├── datasets/             # 数据集管理
│   │   │   ├── __init__.py
│   │   │   ├── dataset_manager.py # 数据集管理器
│   │   │   └── golden/           # Golden Samples
│   │   │       └── samples.json  # 30个标准样本
│   │   └── monitoring/           # 监控与告警
│   │       ├── __init__.py
│   │       ├── metrics_exporter.py # Prometheus指标导出
│   │       ├── alert_manager.py   # 告警管理器
│   │       └── dashboard.py       # 仪表盘数据
│   ├── utils/                    # 工具函数
│   │   └── field_mapping.py      # 字段映射
│   ├── frontend/                 # React前端
│   ├── app.py                    # FastAPI应用 (~1077行)
│   ├── run.py                    # 运行脚本
│   └── config.py                 # 配置管理 (~148行)
├── supply_chain_agent/data/      # Python数据模块
│   ├── supply_chain.db           # SQLite 业务数据库 (运行时)
│   ├── vector_store/             # ChromaDB 向量存储 (SOP 文档)
│   ├── agent_memory.db           # SQLite 记忆数据库
│   ├── data_loader.py            # 数据加载器
│   ├── init_data.py              # 数据初始化脚本
│   └── supply_chain_db.py        # 数据库操作模块 (~1426行)
├── dataset/                      # 数据源目录
│   ├── BusinessData/             # 业务数据源
│   │   └── DataCoSupplyChainDataset.csv
│   ├── SOPData/                  # SOP 文档源
│   │   ├── Supply Chain Business Approval Management Measures.md
│   │   └── Customer Classification and Performance Quota Management Measures.md
│   ├── OtherData/                # 其他数据源
│   │   ├── EntityMapping.csv     # 实体同义词映射
│   │   ├── FallbackResponseTemplate.csv  # 降级响应模板
│   │   └── config.yaml           # Agent 配置
│   ├── DATA_ARCHITECTURE.md      # 数据架构规范
│   └── README.md                 # 数据描述
├── docs/                         # 文档目录
└── .claude/                      # Claude Code配置
```

---

## 2. 系统架构设计

### 2.1 四Agent星型拓扑架构

系统采用**星型拓扑结构**，由一个总控Agent协调三个子Agent：

```
                    ┌─────────────────┐
                    │   Orchestrator  │
                    │   (总控Agent)    │
                    └────────┬────────┘
                             │
           ┌─────────────────┼─────────────────┐
           │                 │                 │
           ▼                 ▼                 ▼
    ┌─────────────┐   ┌─────────────┐   ┌─────────────┐
    │   Parser    │   │  Executor   │   │  Auditor    │
    │  (解析师)   │   │  (调度员)   │   │  (审计员)   │
    └─────────────┘   └─────────────┘   └─────────────┘
```

**职责分工**：

| Agent | 职责 | 输入 | 输出 | 代码行数 |
|-------|------|------|------|----------|
| **Orchestrator** | 全局状态管理、上下文窗口管理、子Agent调度 | 用户输入 | 最终响应 | ~650行 |
| **Parser** | 意图识别、实体提取、槽位填充 | 用户文本 | 结构化意图 | ~830行 |
| **Executor** | 工具编排、并发控制、结果收集 | 执行计划 | 工具结果 | ~1087行 |
| **Auditor** | 结果验证、风控拦截、一致性检查 | 工具结果 | 审计报告 | ~334行 |

### 2.2 LangGraph工作流状态机

系统基于LangGraph构建了一个**8节点状态机**：

```
┌─────────────┐
│ parse_input │ ─────────────────────────────────────────┐
└──────┬──────┘                                          │
       │                                                 │
       ▼ (needs_clarification)                          │
┌─────────────┐                                          │
│   clarify   │ ─────────────────────────────────────────┤
└──────┬──────┘                                          │
       │ (continue)                                      │
       ▼                                                 │
       ┌─────────────────────────────────────────────────┘
       │
       ▼ (no_clarification)
┌─────────────┐
│  plan_task  │
└──────┬──────┘
       │
       ▼
┌─────────────┐     ┌─────────────┐
│execute_task │ ◄── │   retry     │
└──────┬──────┘     └──────┬──────┘
       │                   │
       │ (continue)        │ (retry)
       └───────────────────┘
       │
       ▼ (execution_complete)
┌─────────────┐
│    audit    │
└──────┬──────┘
       │
       ▼ (audit_passed)
┌─────────────┐
│generate_report│
└──────┬──────┘
       │
       ▼
     [END]
```

**节点详细说明**：

1. **parse_input**: 解析用户意图，提取实体
2. **clarify**: 处理缺失信息，使用interrupt等待用户输入
3. **plan_task**: 根据意图生成执行计划
4. **execute_task**: 执行工具调用（支持链式执行模式）
5. **retry**: 处理失败任务的重试逻辑
6. **audit**: 验证执行结果
7. **generate_report**: 生成最终响应
8. **handle_error**: 错误处理节点

### 2.3 三层架构视图

```
┌─────────────────────────────────────────────────────────────┐
│                      用户界面层                              │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐       │
│  │  CLI    │  │  Web    │  │  REST   │  │WebSocket│       │
│  │ 命令行  │  │  界面   │  │  API    │  │  实时流  │       │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘       │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                     Agent服务层                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              Orchestrator (总控)                     │   │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌───────┐ │   │
│  │  │ Parser  │  │Executor │  │ Auditor │  │Report │ │   │
│  │  │ 解析师  │  │ 调度员  │  │ 审计员  │  │Generator│ │   │
│  │  └─────────┘  └─────────┘  └─────────┘  └───────┘ │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              LangGraph Workflow                      │   │
│  │         (状态机 + 检查点 + 中断处理)                  │   │
│  └─────────────────────────────────────────────────────┘   │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                     工具与数据层                             │
│  ┌─────────────────┐  ┌─────────────────┐                  │
│  │   MCP Tools     │  │  Memory System  │                  │
│  │ ┌─────────────┐ │  │ ┌─────────────┐ │                  │
│  │ │query_order  │ │  │ │ Short-term  │ │                  │
│  │ │query_shipment│ │  │ │ Working     │ │                  │
│  │ │query_customer│ │  │ │ Long-term   │ │                  │
│  │ │create_order │ │  │ └─────────────┘ │                  │
│  │ │report_issue │ │  │                 │                  │
│  │ └─────────────┘ │  │ ┌─────────────┐ │                  │
│  └─────────────────┘  │ │  ChromaDB   │ │                  │
│                       │ │  SQLite     │ │                  │
│                       │ └─────────────┘ │                  │
│                       └─────────────────┘                  │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. 核心模块详解

### 3.1 OrchestratorAgent（总控Agent）

**文件位置**: `supply_chain_agent/agents/orchestrator.py`

**核心职责**：
- 依赖注入管理：管理子Agent的创建和注入
- 高层API封装：提供简洁的process()接口
- 响应处理：提取和格式化最终响应
- 错误协调：协调工作流错误，生成降级响应

**已移至Workflow类的职责**：
- 工作流控制逻辑（process_with_events, resume_with_events）
- 节点元数据定义（NODE_METADATA）
- 事件发送逻辑

**关键方法**：

```python
class OrchestratorAgent:
    async def process(self, user_input: str, thread_id: str) -> Dict[str, Any]:
        """
        主处理流程（委托给process_with_callback）
        """
    
    async def process_with_callback(self, user_input: str, callback: Callable):
        """
        委托给Workflow的事件处理方法
        1. 检查是否从clarification恢复
        2. 调用workflow.process_with_events()或workflow.resume_with_events()
        3. 检查interrupt信息
        4. 提取并返回响应
        """
    
    def _extract_interrupt_info(self, interrupt_info: Any) -> tuple:
        """提取中断信息"""
```

**依赖注入设计**：
```python
def __init__(self, 
             parser: Optional[ParserAgent] = None,
             executor: Optional[ExecutorAgent] = None,
             auditor: Optional[AuditorAgent] = None,
             report_generator: Optional[ReportGenerator] = None):
    """
    支持依赖注入，便于测试和解耦
    通过ServiceContainer获取依赖
    """
```

### 3.2 ParserAgent（解析师Agent）

**文件位置**: `supply_chain_agent/agents/parser.py`

**核心职责**：
- 三级意图识别（规则引擎优先）
- 实体提取（BERT NER）
- 槽位填充
- 模糊输入处理

**意图识别分层架构**：

| 层级 | 组件 | 职责 | 触发条件 |
|------|------|------|----------|
| **第一层** | 规则引擎 | 意图模式匹配（一级+二级）+ 规则实体提取 + 置信度计算 | 始终执行 |
| **第二层** | BERT NER | NER实体提取 | `_should_trigger_ner()`: 置信度<0.75 或 实体为空 |
| **第三层** | LLM | 意图分类 + 实体提取 | `_should_trigger_llm()`: 置信度<0.7 或 需要实体但无实体 |

**明确的三层触发条件判断**：
```python
def _can_skip_further_layers(self, confidence, entities, intent_level_1, intent_level_2) -> bool:
    """判断是否可以跳过后续层（快速路径）"""
    # 条件：置信度 >= 0.75 且有实体，或意图类型不需要复杂实体提取

def _should_trigger_ner(self, confidence, entities) -> bool:
    """判断是否触发NER层"""
    # 条件：置信度 < 0.75 或 实体为空

def _should_trigger_llm(self, confidence, entities, intent_level_1, intent_level_2) -> bool:
    """判断是否触发LLM层"""
    # 条件：置信度 < 0.7 或 需要实体但无实体
```

**分离的实体提取方法**：
```python
def _extract_entities_by_rules(self, text, intent_level_1) -> List[Dict]:
    """仅使用规则提取实体（第一层）"""

def _extract_entities_by_ner(self, text, intent_level_1) -> List[Dict]:
    """仅使用BERT NER提取实体（第二层）"""

def _merge_entities(self, base_entities, new_entities) -> List[Dict]:
    """合并实体列表，避免重复"""
```

**任务分类体系**：

| 一级意图 | 说明 | 二级意图 | 对应MCP工具 |
|----------|------|----------|-------------|
| **信息查询** | 查询客户、订单、产品、物流等信息 | 客户查询 | query_customer |
| | | 客户订单查询 | query_customer_orders |
| | | 订单查询 | query_order |
| | | 订单明细查询 | query_order_items |
| | | 产品查询 | query_product |
| | | 物流查询 | query_shipment |
| | | 客户统计查询 | query_customer_statistics |
| | | 工单查询 | query_work_order |
| **工单管理** | 创建和审批工单 | 创建工单 | create_work_order |
| | | 审批工单 | approve_work_order |
| **异常上报** | 上报供应链过程中的问题 | 上报问题 | report_issue |

**置信度计算规则**：
```python
def _calculate_confidence(self, text: str, intent_level_1: str, intent_level_2: str) -> float:
    """
    计算意图识别置信度（仅基于规则匹配，不依赖实体）
    
    置信度计算规则：
    - 基础分: 0.4
    - 一级意图模式命中: +0.2
    - 二级意图关键词命中: +0.2
    - 文本长度合理(>=5): +0.1
    - 短文本惩罚(<5): -0.1
    """
```

### 3.3 ExecutorAgent（调度员Agent）

**文件位置**: `supply_chain_agent/agents/executor.py`

**核心职责**：
- 工具编排
- 并发控制
- 智能重试
- 熔断保护
- 参数验证

**MCP工具参数定义**：
```python
TOOL_PARAMS = {
    "query_customer": {"required": ["customer_id"], "optional": []},
    "query_customer_orders": {"required": ["customer_id"], "optional": ["limit", "offset"]},
    "query_order": {"required": ["order_id"], "optional": []},
    "query_order_items": {"required": ["order_id"], "optional": []},
    "query_product": {"required": ["product_card_id"], "optional": []},
    "query_shipment": {"required": ["order_id"], "optional": []},
    "query_customer_statistics": {"required": ["customer_id"], "optional": []},
    "query_work_order": {"required": ["work_order_id"], "optional": []},
    "create_work_order": {"required": ["work_type", "description"], "optional": ["priority", "order_id", "assigned_to"]},
    "approve_work_order": {"required": ["work_order_id", "action"], "optional": ["comment", "approver"]},
    "report_issue": {"required": ["issue_type", "description"], "optional": ["urgency", "affected_order", "reported_by"]},
}
```

**有效值定义**：
```python
VALID_WORK_TYPES = ["审批", "异常处理", "退款", "调拨", "质检", "其他"]
VALID_PRIORITIES = ["高", "中", "低"]
VALID_ISSUE_TYPES = ["物流延迟", "库存异常", "质量缺陷", "数据错误", "客户投诉", "其他"]
VALID_URGENCIES = ["高", "中", "低"]
VALID_APPROVE_ACTIONS = ["approve", "reject", "escalate"]
```

**工具编排类方法**：

```python
async def execute_plan_with_llm_feedback(
    self,
    execution_plan: List[str],
    initial_slots: Dict[str, Any],
    intent: Dict[str, Any]
) -> Dict[str, Any]:
    """
    执行工具计划，每一步使用规则提取从结果中获取下一步工具的入参。
    
    流程：
    1. 依次执行每个工具
    2. 每执行完一个工具，使用规则从结果中提取下一步工具所需参数
    3. 结合入参和当前待执行工具，继续工具执行
    4. 直至执行计划的所有工具执行完毕，或抛出异常退出
    """

def _extract_params_for_next_tool(
    self,
    current_tool: str,
    current_result: Dict[str, Any],
    next_tool: str,
    current_slots: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """
    使用规则从当前工具执行结果中提取下一个工具的参数（V2.6新增）
    
    参数提取规则映射表：
    - (query_work_order, query_order): order_id -> order_id
    - (query_work_order, query_customer_statistics): customer_id -> customer_id
    - (query_order, query_customer_statistics): customer_id -> customer_id
    """
```

**审批分析类方法（V2.6新增）**：

```python
async def generate_approval_analysis(
    self,
    work_order_id: str,
    tool_results: Dict[str, Any]
) -> Dict[str, Any]:
    """
    生成审批分析报告
    
    在所有查询工具执行完毕后，调用LLM分析查询结果和SOP文档，
    给出审批建议（风险等级、审批层级、建议操作等）。
    """

def _extract_key_fields(self, data: Dict, key_fields: List[str]) -> Dict:
    """从数据中提取关键字段（精简数据，减少token消耗）"""

def _load_sop_document(self, filename: str) -> str:
    """加载SOP文档内容（精简版）"""

def _extract_sop_key_rules(self, content: str, filename: str) -> str:
    """从SOP文档中提取关键规则"""

def _get_fallback_analysis(self, work_order_id: str, tool_results: Dict, error: str) -> Dict:
    """生成降级分析结果（当LLM不可用时）"""
```

### 3.4 AuditorAgent（审计员Agent）

**文件位置**: `supply_chain_agent/agents/auditor.py`

**核心职责**：
- 结果验证
- 风控拦截
- 数据一致性检查
- 业务逻辑验证

**审计规则**：
```python
AUDIT_RULES = [
    AuditRule(name="missing_tracking_number", severity="high", action="reject"),
    AuditRule(name="unusual_delivery_time", severity="medium", action="warn"),
    AuditRule(name="order_cancelled", severity="medium", action="warn"),
    AuditRule(name="high_value_order", severity="low", action="notify"),
    AuditRule(name="approval_without_comment", severity="medium", action="reject"),
]
```

**审计维度**：
1. **字段完整性检查**：必填字段是否存在
2. **状态有效性检查**：状态值是否在合法范围内
3. **跨结果一致性**：多个工具结果是否一致
4. **业务逻辑验证**：是否符合业务规则

### 3.5 LLMClient（LLM客户端）

**文件位置**: `supply_chain_agent/agents/llm_client.py`

**支持的LLM提供商**：
- **智谱AI (ZhipuClient)**：默认使用GLM-4.7模型
- **OpenAI兼容API (OpenAIClient)**：支持自定义模型

**核心方法**：
```python
class LLMClient(ABC):
    @abstractmethod
    async def generate(self, prompt: str) -> str:
        """生成文本响应"""
        pass

    @abstractmethod
    async def generate_json(self, prompt: str, schema: Optional[Dict] = None) -> Dict:
        """生成JSON格式响应"""
        pass
```

**快速生成模式（V2.5新增）**：
```python
async def generate_json_fast(self, prompt: str, max_tokens: int = 1024) -> Dict:
    """
    快速生成JSON格式响应（优化版）

    用于简单的结构化输出任务，关闭 thinking 模式，减少 token 数量。

    优化措施：
    - thinking_override=False: 关闭推理模式
    - max_tokens_override: 限制输出长度（默认512）
    - 自动检测输出截断并重试（双倍token）
    """
```

**Skill 集成**：
```python
async def generate_with_skill(
    self,
    prompt: str,
    skill_name: str,
    additional_context: Optional[Dict[str, Any]] = None,
    fast_mode: bool = True,
    max_tokens: int = 1024
) -> Dict:
    """
    带 skill 上下文生成响应

    自动加载 skill 内容并构建上下文 prompt。
    """
```

**性能对比**：

| 模式 | thinking | max_tokens | 典型耗时 |
|------|----------|------------|----------|
| 普通模式 | 启用 | 65536 | ~35秒 |
| 快速模式 | 禁用 | 512-1024 | ~5秒 |

### 3.6 BERT NER模块

**文件位置**: `supply_chain_agent/nlp/bert_ner.py`

**模型信息**：
- **模型**: bert-base-chinese-wwm (中文全词遮罩预训练模型)
- **路径**: `supply_chain_agent/models/bert-chinese-wwm/`
- **大小**: ~393MB
- **设备**: 支持GPU加速

**实体类型定义**：
```python
ENTITY_LABELS = [
    "O",        # 非实体
    "B-ORDER",  # 订单号开始
    "I-ORDER",  # 订单号内部
    "B-CUSTOMER",  # 客户ID开始
    "I-CUSTOMER",  # 客户ID内部
    "B-PRODUCT",   # 产品ID开始
    "I-PRODUCT",   # 产品ID内部
    "B-WORKORDER", # 工单号开始
    "I-WORKORDER", # 工单号内部
    "B-AMOUNT",    # 金额开始
    "I-AMOUNT",    # 金额内部
    "B-DATE",      # 日期开始
    "I-DATE",      # 日期内部
]
```

### 3.7 ReportGenerator（报告生成器）

**文件位置**: `supply_chain_agent/agents/report_generator.py`

**核心职责**：
- 生成结构化报告
- 构建多模态响应卡片
- 格式化输出
- 降级响应生成

**响应卡片结构**：
```python
{
    "summary": "一句话总结",
    "intent": "意图类型",
    "sections": [
        {"title": "订单信息", "content": "..."},
        {"title": "物流信息", "content": "..."}
    ],
    "actions": [
        {"label": "追踪订单", "action": "track_order"},
        {"label": "联系承运商", "action": "contact_carrier"}
    ]
}
```

---

## 4. 技术栈分析

### 4.1 后端技术栈

| 技术 | 版本 | 用途 |
|------|------|------|
| **Python** | 3.9+ | 主要编程语言 |
| **LangGraph** | 0.2.0+ | 多Agent编排和状态管理 |
| **LangChain** | 0.2.0+ | LLM应用框架 |
| **FastAPI** | 0.110.0+ | REST API框架 |
| **FastMCP** | 0.1.0+ | MCP工具服务 |
| **ChromaDB** | 0.5.0+ | 向量存储 |
| **Pydantic** | 2.0.0+ | 数据验证 |
| **Transformers** | 5.9.0+ | BERT模型加载 |
| **PyTorch** | 2.8.0+ | 深度学习框架 |
| **Uvicorn** | 0.30.0+ | ASGI服务器 |
| **httpx** | - | 异步HTTP客户端 |

### 4.2 LLM集成

**默认配置**：智谱AI GLM-4.7

```python
# config.py
llm_provider: str = "zhipu"
llm_model: str = "glm-4.7"
llm_base_url: str = "https://open.bigmodel.cn/api/paas/v4"
llm_temperature: float = 0.7
llm_max_tokens: int = 65536
```

**LLM使用场景**：
1. 意图识别（模糊输入处理）
2. 实体提取（补充规则无法识别的实体）
3. 降级响应生成（工具不可用时）
4. 链式执行参数解析

### 4.3 前端技术栈

| 技术 | 版本 | 用途 |
|------|------|------|
| **React** | 18.2.0 | UI框架 |
| **TypeScript** | 5.3.0 | 类型安全 |
| **Ant Design** | 5.12.0 | 企业级UI组件 |
| **Vite** | 5.0.0 | 构建工具 |
| **Zustand** | 4.4.0 | 状态管理 |
| **React Router** | 6.20.0 | 路由管理 |
| **Axios** | 1.6.0 | HTTP客户端 |
| **ECharts** | 5.4.0 | 图表可视化 |
| **React Markdown** | 9.0.0 | Markdown渲染 |

### 4.4 存储技术栈

| 存储 | 用途 | 数据类型 |
|------|------|----------|
| **SQLite** | 关系存储 | 业务数据、工单记录、实体映射、降级模板、配置 |
| **ChromaDB** | 向量存储 | SOP 文档 (从 dataset/SOPData/ 加载) |
| **JSON文件** | 检查点存储 | LangGraph状态持久化 |

---

## 5. 工作流程机制

### 5.1 LangGraph状态定义

**文件位置**: `supply_chain_agent/graph/state.py`

```python
class AgentState(TypedDict):
    # 对话历史
    messages: Annotated[List[Dict[str, str]], operator.add]
    
    # 用户意图和提取信息
    user_intent: Dict[str, Any]
    extracted_slots: Dict[str, Any]
    missing_slots: List[str]
    
    # 任务执行
    task_queue: List[str]
    current_task: Optional[str]
    tool_results: Dict[str, Any]
    
    # 审计和验证
    audit_results: Dict[str, Any]
    validation_errors: List[str]
    
    # 记忆和上下文
    context_window: List[Dict[str, Any]]
    long_term_memory_refs: List[str]
    
    # 错误处理
    error_count: int
    last_error: Optional[str]
    circuit_breakers: Dict[str, Dict[str, Any]]
    
    # 错误代码和模板参数
    error_code: Optional[str]
    error_template_params: Dict[str, Any]
    from_error_handler: bool
    
    # 最终输出
    final_report: Optional[Dict[str, Any]]
    response_card: Optional[Dict[str, Any]]
    
    # Human-in-the-loop
    waiting_for_input: bool
    clarification_prompt: Optional[str]
    clarification_received: bool
    clarification_loop_count: int
    max_clarification_reached: bool
```

### 5.2 工作流边逻辑

**条件分支函数**：

```python
def _check_clarification_needed(state: AgentState) -> str:
    """检查是否需要澄清"""
    if len(state.get("missing_slots", [])) > 0:
        return "needs_clarification"
    return "no_clarification"

def _check_execution_status(state: AgentState) -> str:
    """检查执行状态"""
    if state.get("execution_failed", False):
        return "execution_failed"
    if not state.get("task_queue", []):
        return "execution_complete"
    return "continue_execution"

def _check_audit_result(state: AgentState) -> str:
    """检查审计结果"""
    if state.get("audit_results", {}).get("passed", False):
        return "audit_passed"
    return "audit_failed"
```

### 5.3 Interrupt机制

**澄清处理**：
```python
async def clarify_node(state: AgentState) -> Dict[str, Any]:
    # 检查循环计数
    if state.get("clarification_loop_count", 0) >= 3:
        return {"max_clarification_reached": True}

    # 使用interrupt暂停执行
    interrupt_data = {
        "type": "clarification_required",
        "prompt": response,
        "missing_slots": state["missing_slots"]
    }
    user_input = interrupt(interrupt_data)

    # 返回更新后的状态
    return {
        "messages": state["messages"] + [
            {"role": "assistant", "content": response},
            {"role": "user", "content": user_input}
        ]
    }
```

### 5.4 实时事件流（V2.5新增）

**使用 `astream_events` 实现节点实时进度显示**：

```python
async def process_with_events(self, user_input: str, emit_event: Callable):
    """
    使用 astream_events 实现实时进度显示

    关键改进：
    - on_chain_start: 节点开始时立即发送 step_start 事件
    - on_chain_end: 节点结束时发送 step_end 事件
    """
    async for event in self.graph.astream_events(initial_state, config=config, version="v2"):
        event_kind = event.get("event")

        if event_kind == "on_chain_start":
            # 节点开始执行，立即显示
            await emit_event("step_start", {
                "stepId": node_name,
                "title": metadata.get("title"),
                "description": metadata.get("description")
            })

        elif event_kind == "on_chain_end":
            # 节点执行完成
            await emit_event("step_end", {
                "stepId": node_name
            })
```

**事件回调传播**：

```python
# workflow.py 中设置事件回调
async def plan_task_node(state: AgentState) -> Dict[str, Any]:
    if self.executor:
        if hasattr(self.executor, 'set_emit_event'):
            self.executor.set_emit_event(self._current_emit_event)
    # ... 节点逻辑
```

**前端事件处理**：

```typescript
// conversationStore.ts
handleAgentEvent: (event) => {
  switch (event.type) {
    case 'step_start':
      // 立即添加步骤到轨迹
      addAgentStep({ id: stepId, status: 'running', ... });
      break;
    case 'step_end':
      // 更新步骤状态为成功
      updateAgentStep(stepId, { status: 'success' });
      break;
    case 'skill_load':
      // 处理 Skill 加载事件
      // 使用 pendingSkills 处理事件顺序问题
      break;
  }
}
```

**PendingSkills 机制**：

处理 Skill 事件可能在 step_start 之前到达的情况：

```typescript
// 使用 Map 存储待关联的 skills
pendingSkills: Map<string, SkillCall[]>

// step_start 时检查并关联
const pendingSkillsForStep = get().pendingSkills.get(stepPrefix) || [];
get().addAgentStep({
  id: newStepId,
  skills: pendingSkillsForStep,  // 使用待关联的 skills
});
```

---

## 6. 记忆系统设计

### 6.1 三层记忆架构

```
┌─────────────────────────────────────────────────────────────┐
│                    短期记忆 (Short-term)                     │
│  • 滑动窗口存储最近20条对话                                  │
│  • 支持摘要压缩防止Token溢出                                 │
│  • 存储操作记录和Agent行为                                   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    工作记忆 (Working)                        │
│  • LangGraph共享状态 (AgentState)                           │
│  • 所有Agent读写互斥                                        │
│  • 支持检查点持久化                                          │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    长期记忆 (Long-term)                      │
│  ┌─────────────────────┐  ┌─────────────────────┐          │
│  │      ChromaDB       │  │       SQLite        │          │
│  │ • SOP手册 (7条)     │  │ • 工单处理记录      │          │
│  │ • FAQ知识库 (3条)   │  │ • 工具使用统计      │          │
│  │ • 知识库 (备用)     │  │ • 记忆项存储        │          │
│  └─────────────────────┘  └─────────────────────┘          │
└─────────────────────────────────────────────────────────────┘
```

### 6.2 ShortTermMemory实现

**文件位置**: `supply_chain_agent/memory/vector_store.py`

```python
class ShortTermMemory:
    def __init__(self, window_size: int = 20):
        self.window_size = window_size
        self.memory_window: List[MemoryItem] = []
        self.summary_cache: Optional[str] = None
    
    def add(self, content: Dict, tags: List[str], importance: float):
        """添加记忆项，维护滑动窗口"""
        
    def get_summary(self) -> str:
        """生成摘要，防止Token溢出"""
        
    def get_recent(self, limit: int) -> List[Dict]:
        """获取最近的记忆项"""
```

### 6.3 LongTermMemory实现

**文件位置**: `supply_chain_agent/memory/vector_store.py`

#### ChromaDB向量存储

| 集合名称 | 用途 | 数据来源 |
|----------|------|----------|
| `sop_manual` | 标准操作流程 | `dataset/SOPData/*.md` |
| `faq` | 常见问题解答 | 内置 |
| `knowledge_base` | 知识库(备用) | 运行时添加 |

#### SQLite记忆数据库

**数据库文件**: `supply_chain_agent/data/agent_memory.db`

| 表名 | 用途 | 说明 |
|------|------|------|
| `memory_items` | 记忆项存储 | 对话/操作记忆 |
| `tool_usage_stats` | 工具使用统计 | 成功/失败次数、耗时 |
| `work_order_records` | 工单处理记录 | 完整处理流程记录 |

---

## Skill 系统

Supply-Chain-Agent 使用 Skill 系统指导 LLM 完成特定任务。Skill 采用渐进式披露（Progressive Disclosure）的上下文工程技术。

### 审批工单 Skill

当检测到审批工单意图时，系统自动加载 `approval_workflow` skill：

- **位置**: `supply_chain_agent/skills/approval_workflow/`
- **触发条件**: `intent_level_2 = "审批工单"`
- **功能**: 指导 LLM 生成执行计划、提取参数、执行工具

### 审批工单分析流程（V2.6新增）

审批工单意图采用**LLM分析推荐+用户确认**模式，实现智能化审批辅助决策：

**工作流程**：
1. **意图识别**：只需提供 `work_order_id`，无需提前指定审批动作
2. **工具链执行**：依次执行 `query_work_order` → `query_order` → `query_customer_statistics`
3. **规则参数提取**：工具间参数传递使用规则提取，无需LLM解析
4. **LLM分析**：查询完成后，LLM结合SOP文档进行风险分析和审批建议
5. **用户确认**：前端展示分析结果，用户决定审批动作（approve/reject/escalate）

**技术实现**：

```python
# executor.py 新增方法
async def generate_approval_analysis(
    self,
    work_order_id: str,
    tool_results: Dict[str, Any]
) -> Dict[str, Any]:
    """
    生成审批分析报告
    
    流程：
    1. 加载SOP文档（精简版）
    2. 提取查询结果关键字段
    3. 调用LLM分析风险和审批建议
    4. 返回结构化分析结果
    """

def _extract_params_for_next_tool(
    self,
    current_tool: str,
    current_result: Dict[str, Any],
    next_tool: str,
    current_slots: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """
    使用规则从当前工具执行结果中提取下一个工具的参数
    
    参数提取规则映射表：
    - (query_work_order, query_order): order_id -> order_id
    - (query_work_order, query_customer_statistics): customer_id -> customer_id
    - (query_order, query_customer_statistics): customer_id -> customer_id
    """
```

**技术特点**：
- **规则参数提取**：`_extract_params_for_next_tool()` 方法定义字段映射规则，替代LLM解析，降低token消耗
- **LLM分析优化**：精简Prompt模板（~2000字符），提取关键字段减少token消耗
- **SOP文档精简**：`_extract_sop_key_rules()` 只提取关键规则章节
- **前端展示**：显示LLM分析结果（风险等级、审批建议、置信度），而非原始查询数据

**审批分析Prompt模板**：

```python
APPROVAL_ANALYSIS_PROMPT = """你是供应链审批专家。根据查询结果和规则，给出审批建议。

## 工单: {work_order_id}
## 查询结果
**工单**: {work_order_result}
**订单**: {order_result}
**客户**: {customer_statistics_result}

## 审批规则
### 客商风险等级
- A级(优质): 企业客户，履约良好，额度>50000
- B级(良好): 企业客户，偶有延迟，额度20000-50000
...

## 输出要求
输出JSON: {summary, risk_level, risk_factors, approval_level, recommendation, confidence}
"""
```

**状态管理更新**：

```python
class AgentState(TypedDict):
    # ... 其他字段
    approval_analysis: Optional[Dict[str, Any]]  # V2.6新增：审批分析结果
```

**报告生成优化**：

```python
# report_generator.py
async def generate_report(
    self,
    intent: Dict[str, Any],
    tool_results: Dict[str, Any],
    audit_results: Dict[str, Any],
    approval_analysis: Dict[str, Any] = None  # V2.6新增
) -> Dict[str, Any]:
    """
    审批工单：不添加查询工具结果，只使用分析结果
    """
```

**前端展示内容**：

| 展示区块 | 内容 |
|---------|------|
| 📋 工单概况 | 工单类型、状态、优先级、订单金额、客户信息 |
| ⚠️ 风险评估 | 风险等级（A/B/C/D/E级）、风险因素 |
| 📑 审批要求 | 审批层级、材料状态、特殊条件 |
| 💡 审批建议 | 建议操作（通过/拒绝/上报）、理由、风险提示 |
| 📊 分析置信度 | LLM分析置信度百分比 |

**用户操作按钮**：

根据LLM建议动态生成确认按钮：
- 建议通过 → "✅ 确认通过"
- 建议拒绝 → "❌ 确认拒绝"
- 建议上报 → "⬆️ 上报审批"
- 始终提供 → "🔄 选择其他操作"、"📝 修改审批意见"

### Skill 结构

```
skills/
└── approval_workflow/
    ├── SKILL.md              # 主 skill 文件
    └── procedures/           # 渐进式披露子流程
        ├── plan_generation.md
        ├── param_extraction.md
        └── tool_execution.md
```

### 配置选项

通过环境变量配置 Skill 行为：

| 环境变量 | 默认值 | 说明 |
|---------|-------|------|
| `SCA_USE_SKILL_FOR_APPROVAL` | `true` | 启用 skill 模式处理审批工单 |
| `SCA_SKILL_FALLBACK_TO_PROMPT` | `true` | skill 加载失败时降级到 prompt |

### 工作原理

1. **意图识别**: ParserAgent 识别用户意图为"审批工单"
2. **Skill 加载**: ExecutorAgent 通过 LLMClient 加载 approval_workflow skill
3. **执行计划生成**: LLM 根据 skill 指导生成执行计划
4. **Fallback 机制**: 如果 skill 加载失败，自动降级到 prompt 模式

### LLM 快速生成模式

为优化 Skill 加载性能，`LLMClient` 提供快速生成模式：

```python
async def generate_json_fast(self, prompt: str, max_tokens: int = 1024) -> Dict:
    """
    快速生成JSON格式响应（优化版）

    - 关闭 thinking 模式，减少推理时间
    - 减少 max_tokens（默认512），加快生成速度
    - 自动检测输出截断并重试
    """
```

**性能优化效果**：
- Skill 加载时间从 ~35秒 降至 ~5秒
- 适用于简单的结构化输出任务

### 前端 Skill 加载显示

前端 Agent 执行轨迹面板实时显示 Skill 加载过程：

- **实时事件流**: 使用 LangGraph `astream_events` API 实现节点进入时立即显示
- **Skill 卡片**: 与工具调用卡片风格一致，显示加载状态、耗时、结果
- **PendingSkills 机制**: 处理事件顺序问题，确保 Skill 正确关联到对应步骤

---

## 7. MCP工具系统

### 7.1 工具定义

**文件位置**: `supply_chain_agent/tools/server.py`

**信息查询类工具**：

| 工具名称 | 功能 | 必需参数 | 可选参数 |
|----------|------|----------|----------|
| `query_customer` | 查询客户基本信息 | customer_id | - |
| `query_customer_orders` | 查询客户订单列表 | customer_id | limit, offset |
| `query_order` | 查询订单详情 | order_id | - |
| `query_order_items` | 查询订单明细 | order_id | - |
| `query_product` | 查询产品信息 | product_card_id | - |
| `query_shipment` | 查询物流信息 | order_id | - |
| `query_customer_statistics` | 查询客户统计 | customer_id | - |
| `query_work_order` | 查询工单详情 | work_order_id | - |

**工单管理类工具**：

| 工具名称 | 功能 | 必需参数 | 可选参数 |
|----------|------|----------|----------|
| `create_work_order` | 创建工单 | work_type, description | priority, order_id, assigned_to |
| `approve_work_order` | 审批工单 | work_order_id, action | comment, approver |

**异常上报类工具**：

| 工具名称 | 功能 | 必需参数 | 可选参数 |
|----------|------|----------|----------|
| `report_issue` | 上报问题 | issue_type, description | urgency, affected_order, reported_by |

### 7.2 工具有效值定义

```python
# 工单类型
VALID_WORK_TYPES = ["审批", "异常处理", "退款", "调拨", "质检", "其他"]

# 优先级
VALID_PRIORITIES = ["高", "中", "低"]

# 问题类型
VALID_ISSUE_TYPES = ["物流延迟", "库存异常", "质量缺陷", "数据错误", "客户投诉", "其他"]

# 紧急程度
VALID_URGENCIES = ["高", "中", "低"]

# 审批动作
VALID_APPROVE_ACTIONS = ["approve", "reject", "escalate"]
```

### 7.3 工具客户端熔断机制

**文件位置**: `supply_chain_agent/tools/client.py`

```python
class ToolClient:
    def _check_circuit_breaker(self, tool_name: str) -> bool:
        """检查熔断器状态"""
        breaker = self.circuit_breakers[tool_name]
        
        # 失败次数达到阈值，打开熔断器
        if breaker.failure_count >= settings.circuit_breaker_failures:
            breaker.is_open = True
            breaker.open_until = time.time() + settings.circuit_breaker_reset_timeout
            return False
        
        return not breaker.is_open
```

### 7.4 降级响应机制

当工具不可用时，使用知识库+LLM生成合理提示：

```python
async def _fallback_response(self, user_input: str, intent_info: Dict, error: str):
    """
    降级响应流程：
    1. 知识库检索相关SOP/FAQ
    2. LLM生成友好提示
    3. 明确标记不包含真实数据
    """
    return {
        "fallback": True,
        "message": llm_message,
        "data_available": False  # 明确标记无真实数据
    }
```

---

## 8. 前端界面设计

### 8.1 技术架构

```
┌─────────────────────────────────────────────────────────────┐
│                        React App                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                    AppRoutes                         │   │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐ │   │
│  │  │  Chat   │  │Dashboard│  │  Tools  │  │Settings │ │   │
│  │  │  对话   │  │  仪表盘 │  │  工具   │  │  设置   │ │   │
│  │  └─────────┘  └─────────┘  └─────────┘  └─────────┘ │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                    Zustand Store                     │   │
│  │  • conversationStore  • toolStore  • uiStore        │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                    API Layer                         │   │
│  │  • chatService  • toolService  • statsService       │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### 8.2 页面路由

| 路由 | 页面 | 描述 |
|------|------|------|
| `/` | 首页 | 系统概览 |
| `/chat` | 对话页 | 主要交互界面 |
| `/dashboard` | 仪表盘 | 性能指标展示 |
| `/tools` | 工具页 | 工具管理与测试 |
| `/settings` | 设置页 | 系统配置 |

### 8.3 Agent执行轨迹面板（V2.5增强）

**组件位置**: `supply_chain_agent/frontend/src/components/agent/AgentTrajectory.tsx`

**功能特性**：
- 实时显示 Agent 执行步骤和进度
- Skill 加载卡片（与工具调用风格一致）
- 自动滚动到最新步骤
- 步骤详情 JSON 查看

**Skill 加载显示**：

```typescript
// SkillCallItem 组件
const SkillCallItem = memo(({ skill }: SkillCallItemProps) => {
  return (
    <div style={{ padding: '8px 12px', background: 'var(--bg-tertiary)', borderRadius: 6 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
        <Text strong>{skill.displayName || skill.name}</Text>
        <Tag color={skill.status === 'success' ? 'success' : 'processing'}>
          {duration}
        </Tag>
      </div>
      {skill.result && <pre>生成计划: {skill.result.join(' → ')}</pre>}
    </div>
  );
});
```

**事件类型定义**：

```typescript
// types/agent.ts
interface SkillCall {
  id: string;
  name: string;
  displayName?: string;
  status: 'pending' | 'running' | 'success' | 'error';
  startTime: number;
  endTime?: number;
  result?: string[];
  error?: string;
}

interface AgentStep {
  id: string;
  agentType: AgentType;
  title: string;
  description: string;
  status: 'pending' | 'running' | 'success' | 'error';
  startTime: number;
  endTime?: number;
  tools: ToolCall[];
  skills: SkillCall[];  // 新增：Skill 调用列表
}
```

---

## 9. 评估体系与性能指标

### 9.1 四维评估指标

| 维度 | 指标 | 目标值 | 实际达成 |
|------|------|--------|----------|
| **效果指标** | 任务成功率 | > 65% | **72.0%** |
| **效率指标** | 平均首次响应时长 | < 3秒 | **2.10秒** |
| **体验指标** | 用户采纳率 | > 40% | **61.2%** |
| **稳定性指标** | 工具调用可用率 | > 95% | **96.0%** |

### 9.2 性能优化措施

1. **规则优先策略**: 意图识别优先使用规则引擎，降低LLM调用频率
2. **BERT NER增强**: 中文实体识别准确率提升
3. **熔断器保护**: 防止工具故障级联扩散
4. **滑动窗口**: 控制上下文窗口大小，防止Token溢出
5. **并发控制**: ExecutorAgent支持并发工具调用
6. **检查点持久化**: LangGraph状态持久化，支持断点恢复

---

## 10. 配置与部署

### 10.1 配置管理

**文件位置**: `supply_chain_agent/config.py`

```python
class Settings(BaseSettings):
    # LLM配置
    llm_provider: str = "zhipu"
    llm_model: str = "glm-4.7"
    llm_api_key: str = "..."
    llm_base_url: str = "https://open.bigmodel.cn/api/paas/v4"
    llm_temperature: float = 0.7
    llm_max_tokens: int = 65536
    
    # 意图识别配置
    intent_rule_first: bool = True  # 优先规则快速路径
    intent_confidence_threshold: float = 0.75
    
    # 降级策略
    fallback_strategy: str = "knowledge_first"
    
    # Agent配置
    max_retries: int = 3
    clarification_max_attempts: int = 3

    # 记忆配置
    memory_window_size: int = 20
    vector_store_path: str = "./supply_chain_agent/data/vector_store"
    sqlite_db_path: str = "./supply_chain_agent/data/agent_memory.db"

    # 熔断器配置
    circuit_breaker_failures: int = 5
    circuit_breaker_reset_timeout: int = 300

    # Web配置
    web_port: int = 8000
    debug_mode: bool = True
```

### 10.2 运行模式

| 模式 | 命令 | 用途 |
|------|------|------|
| CLI | `python -m supply_chain_agent --mode cli` | 开发调试 |
| Web | `python -m supply_chain_agent --mode web --port 8000` | 业务使用 |
| MCP | `python -m supply_chain_agent --mode mcp --mcp-port 8001` | 工具服务 |

---

## 11. 性能指标分析

### 11.1 实际性能数据

| 指标 | 目标值 | 实际值 | 状态 |
|------|--------|--------|------|
| 任务成功率 | > 65% | 72.0% | ✅ 达标 |
| 平均响应时间 | < 3秒 | 2.10秒 | ✅ 达标 |
| 用户采纳率 | > 40% | 61.2% | ✅ 达标 |
| 工具可用率 | > 95% | 96.0% | ✅ 达标 |

### 11.2 资源消耗

| 资源 | 最小配置 | 推荐配置 |
|------|----------|----------|
| CPU | 2核心 | 4核心 |
| 内存 | 4GB | 8GB |
| 存储 | 20GB SSD | 50GB SSD |
| GPU | 可选 | 推荐用于BERT NER |

---

## 12. 项目特色与创新点

### 12.1 架构创新

1. **四Agent星型拓扑**: 总控Agent协调三个专业子Agent，职责清晰
2. **LangGraph状态机**: 8节点状态机，支持中断恢复和Human-in-the-loop
3. **三层记忆系统**: 短期+工作+长期记忆，支持RAG检索

### 12.2 技术创新

1. **三层意图识别架构**:
   - 第一层：规则引擎仅做意图模式匹配（一级+二级）+ 置信度计算
   - 第二层：BERT NER专注实体提取
   - 第三层：LLM兜底（意图分类+实体提取）
   - 职责分离清晰，降低LLM调用频率

2. **Skill系统与渐进式披露**:
   - 使用 Skill 指导 LLM 完成特定任务
   - 渐进式披露减少 token 消耗
   - 快速生成模式优化（关闭 thinking，限制 max_tokens）
   - Skill 加载从 ~35秒 优化至 ~5秒

3. **审批工单LLM分析推荐模式（V2.6新增）**:
   - 用户只需提供工单号，无需提前指定审批动作
   - 工具链执行后，LLM结合SOP文档进行风险分析和审批建议
   - 规则参数提取替代LLM解析，降低token消耗
   - 前端展示分析结果（风险等级、审批建议），用户确认后执行
   - 实现智能化审批辅助决策

4. **实时进度显示**:
   - 使用 LangGraph `astream_events` API
   - 节点进入时立即显示，而非完成后显示
   - PendingSkills 机制处理事件顺序问题

5. **熔断器模式**: 工具调用熔断保护，防止故障扩散
6. **知识库降级**: 工具不可用时，知识库检索+LLM生成友好提示，**不返回假数据**
7. **审批二次确认**: 危险操作（审批）必须用户二次确认，V2.6新增LLM分析推荐+用户确认模式

### 12.3 工程实践

1. **依赖注入**: Agent支持依赖注入，便于测试和解耦
2. **事件回调**: 支持WebSocket实时推送Agent执行过程
3. **结构化日志**: 完整的日志记录和监控指标
4. **检查点管理**: LangGraph状态持久化，支持断点恢复

---

## 13. 代码质量分析

### 13.1 代码组织

- **模块化设计**: 各Agent独立模块，职责单一
- **清晰的目录结构**: 按功能分层组织
- **完善的类型注解**: 使用TypedDict和Pydantic进行类型定义

### 13.2 代码统计

| 模块 | 文件 | 代码行数 | 说明 |
|------|------|----------|------|
| Orchestrator | orchestrator.py | ~650 | 总控Agent |
| Parser | parser.py | ~835 | 解析师Agent |
| Executor | executor.py | ~1200 | 调度员Agent（V2.6新增审批分析功能） |
| Auditor | auditor.py | ~334 | 审计员Agent |
| Workflow | workflow.py | ~1050 | LangGraph工作流（V2.6新增审批分析调用） |
| Memory | vector_store.py | ~666 | 记忆系统 |
| App | app.py | ~1077 | FastAPI应用 |
| Database | supply_chain_db.py | ~1426 | 数据库操作 |
| MCP Server | server.py | ~754 | MCP工具服务 |
| MCP Client | client.py | ~490 | 工具客户端 |
| BERT NER | bert_ner.py | ~330 | NER模块 |
| Config | config.py | ~148 | 配置管理 |
| State | state.py | ~240 | 状态定义（V2.6新增approval_analysis字段） |
| Report Generator | report_generator.py | ~550 | 报告生成器（V2.6新增审批分析展示） |
| LLM Client | llm_client.py | ~575 | LLM客户端（含快速生成模式）|
| Prompts | execution_plan.py | ~180 | Prompt模板（V2.6新增审批分析模板） |

**总计**: 约 ~8500 行核心代码

---

## 14. Harness Engineering 工程化能力 (V2.7新增)

### 14.1 设计理念

基于"**Human Steer, Agents Execute**"（人类掌舵，智能体执行）的哲学，Harness Engineering为系统提供三层工程化增强：

```
┌─────────────────────────────────────────────────────────────┐
│          Layer 3: 反馈与持续改进层（Feedback & Iteration）    │
│    • 错误聚类报告（半自动）                                   │
│    • 周度分析流程                                             │
│    • Harness Playbook                                        │
├─────────────────────────────────────────────────────────────┤
│          Layer 2: 验证与可观测层（Verification & Observability）│
│    • 结构化日志（JSON）                                      │
│    • Prometheus Metrics                                     │
│    • 按需Trace（采样+错误全记录）                             │
│    • 核心场景Evals（Level 1/2/3）                           │
├─────────────────────────────────────────────────────────────┤
│          Layer 1: 配置化约束层（Configurable Constraints）    │
│    • 业务规则配置（扩展Auditor）                              │
│    • 参数预检装饰器（可选）                                    │
│    • AGENTS.md + SPEC规范文件                                │
└─────────────────────────────────────────────────────────────┘
```

**核心原则**：增强而非替换，配置化而非框架化，可选而非强制

### 14.2 Layer 1: 配置化约束层

#### 14.2.1 业务规则YAML配置

**文件位置**: `supply_chain_agent/harness/rules/business_rules.yaml`

支持从YAML文件加载业务审计规则，实现热加载：

```yaml
rules:
  - id: "high_value_approval"
    name: "大额审批需升级"
    enabled: true
    severity: "block"
    condition: "work_order.get('amount', 0) > 500000 and work_order.get('type') == '审批'"
    action: "require_approval_level: director"
    message: "订单金额超过50万，需要总监级审批"
```

**安全表达式评估器**:

使用AST解析实现安全表达式评估，防止代码注入：

```python
class SafeExpressionEvaluator:
    """只允许访问预定义变量，使用AST解析而非eval()"""
    
    def evaluate(self, expression: str, context: Dict[str, Any]) -> bool:
        # 支持的操作：比较、逻辑、包含、字典访问
        # 允许的变量：work_order, order, customer, shipment, action, comment
```

#### 14.2.2 参数预检装饰器

**文件位置**: `supply_chain_agent/harness/decorators.py`

为Executor Agent提供可选的参数预检功能：

```python
@with_pre_check([check_required_params, check_param_range])
async def execute_tool(self, tool_name, params):
    # 工具执行逻辑
```

### 14.3 Layer 2: 验证与可观测层

#### 14.3.1 Prometheus Metrics

**文件位置**: `supply_chain_agent/harness/observability/metrics.py`

提供9个标准Prometheus指标：

| 指标名 | 类型 | 描述 |
|--------|------|------|
| `agent_requests_total` | Counter | 总请求数 |
| `agent_request_duration_seconds` | Histogram | 请求延迟 |
| `agent_tool_calls_total` | Counter | 工具调用次数 |
| `agent_tool_call_duration_seconds` | Histogram | 工具调用延迟 |
| `agent_circuit_breaker_state` | Gauge | 熔断器状态 |
| `agent_active_sessions` | Gauge | 活跃会话数 |
| `agent_audit_results_total` | Counter | 审计结果 |
| `agent_rule_trigger_total` | Counter | 规则触发次数 |
| `agent_trace_samples_total` | Counter | Trace采样数 |

**访问方式**:

```bash
curl http://localhost:8000/metrics
```

#### 14.3.2 结构化日志

**文件位置**: `supply_chain_agent/harness/observability/logging_config.py`

输出JSON格式日志，便于采集到ELK/Loki：

```python
logger.info("agent_step", extra={
    "step": "parse_input",
    "thread_id": thread_id,
    "duration_ms": 45
})

# 输出：
# {"timestamp": "2026-06-07T10:00:00Z", "level": "INFO", "message": "agent_step", "step": "parse_input", ...}
```

#### 14.3.3 按需Trace收集

**文件位置**: `supply_chain_agent/harness/observability/trace.py`

特性：
- **采样率控制**：默认1%（通过`HARNESS_TRACE_SAMPLE_RATE`配置）
- **错误全量记录**：任何导致任务失败的执行全量记录
- **存储格式**：JSON Lines，按天分区，保存7天
- **存储位置**：`/root/autodl-tmp/harness-traces/`

**查询工具**:

```bash
# 查询所有错误Trace
python -m supply_chain_agent.harness.observability.trace_cli --status error

# 按Trace ID查询
python -m supply_chain_agent.harness.observability.trace_cli --trace-id abc123
```

#### 14.3.4 Evals评估框架

**文件位置**: `supply_chain_agent/harness/evals/`

提供9个评估器，覆盖意图识别、工具调用、审计、端到端场景：

| 评估器 | 等级 | 描述 |
|--------|------|------|
| `IntentAccuracyEvaluator` | Level 1 (门禁) | 意图识别准确率 |
| `IntentConfidenceEvaluator` | Level 2 (告警) | 意图置信度 |
| `ToolCallAccuracyEvaluator` | Level 1 (门禁) | 工具调用准确率 |
| `ToolParamValidationEvaluator` | Level 1 (门禁) | 参数验证 |
| `ToolExecutionSuccessEvaluator` | Level 2 (告警) | 工具执行成功率 |
| `AuditRuleCoverageEvaluator` | Level 2 (告警) | 审计规则覆盖 |
| `RiskScoreEvaluator` | Level 2 (告警) | 风险评分准确度 |
| `E2EWorkflowEvaluator` | Level 1 (门禁) | 端到端工作流 |
| `E2ELatencyEvaluator` | Level 2 (告警) | 端到端延迟 |

**评估等级**：

| 等级 | 名称 | 说明 |
|------|------|------|
| Level 1 | 门禁级 | 必须通过才能部署 |
| Level 2 | 告警级 | 失败只告警 |
| Level 3 | 手动级 | 可选执行 |

### 14.4 Layer 3: 反馈与持续改进层

#### 14.4.1 错误聚类分析

**文件位置**: `supply_chain_agent/harness/feedback/cluster_errors.py`

自动识别8种错误模式并生成改进建议：

| 错误类型 | 匹配模式 |
|----------|----------|
| MissingParameterError | 缺少必要参数 |
| ToolTimeoutError | timeout/超时 |
| ToolExecutionError | 工具执行失败 |
| IntentParseError | 意图解析错误 |
| ValidationError | 验证失败 |
| CircuitBreakerOpenError | 熔断器打开 |
| ConnectionError | 连接错误 |
| RateLimitError | 限流 |

**使用方式**:

```bash
# 分析最近7天的错误
python -m supply_chain_agent.harness.feedback.cluster_errors --days 7
```

#### 14.4.2 周度报告生成

**文件位置**: `supply_chain_agent/harness/feedback/weekly_report.py`

自动生成Markdown格式的周度分析报告，包含：
- 性能指标概览
- Top 3错误类型
- Evals执行情况
- 改进项跟踪

### 14.5 环境变量配置

所有Harness特性均可通过环境变量独立开关：

```bash
# Layer 1: 配置化约束
export HARNESS_RULES_ENABLED=true           # 启用业务规则审计
export HARNESS_RULES_PATH=/path/to/rules.yaml

# Layer 2: 可观测性
export HARNESS_STRUCTURED_LOGS=true         # 结构化日志
export HARNESS_METRICS_ENABLED=true         # Prometheus Metrics
export HARNESS_TRACE_ENABLED=true           # Trace收集
export HARNESS_TRACE_SAMPLE_RATE=0.01       # 采样率
export HARNESS_TRACE_DIR=/root/autodl-tmp/harness-traces

# Layer 2: Evals
export HARNESS_EVALS_LEVEL=1                # 评估等级

# 可选功能
export HARNESS_PRE_CHECK=false              # 参数预检装饰器
```

### 14.6 性能影响

| 特性 | 性能影响 | 默认状态 |
|------|----------|----------|
| 业务规则审计 | <1ms/规则 | 开启 |
| 结构化日志 | 忽略不计 | 开启 |
| Prometheus Metrics | 忽略不计 | 开启 |
| Trace (1%采样) | 几乎无影响 | 开启 |
| Trace (错误全量) | ~50ms | 仅错误时 |

### 14.7 相关文档

- **Playbook**: `supply_chain_agent/harness/playbook.md` - 完整运维手册
- **系统入口**: `supply_chain_agent/AGENTS.md` - 系统指南
- **设计文档**: `docs/Harness Engineering Design.md` - 详细设计

---

## 15. Agent评估系统 (V2.8新增)

### 15.1 设计理念

基于 `docs/Agent Eval.md` 设计文档，实现完整的Agent评估系统，采用**四层评估架构**：

```
┌─────────────────────────────────────────────────────────────┐
│           Layer 4: 监控与告警（Monitoring & Alerting）        │
│    • Prometheus指标导出                                       │
│    • 仪表盘数据API                                            │
│    • 告警规则管理                                             │
├─────────────────────────────────────────────────────────────┤
│           Layer 3: Harness集成（Harness Integration）         │
│    • 复用Harness Rules评估                                    │
│    • 复用Harness Evals评估器                                  │
│    • 复用Harness错误聚类                                      │
├─────────────────────────────────────────────────────────────┤
│           Layer 2: LLM Judge校准（Calibration）               │
│    • Cohen's Kappa一致性检验                                  │
│    • Golden Samples校准集                                     │
│    • 人机一致性保障                                           │
├─────────────────────────────────────────────────────────────┤
│           Layer 1: 轨迹评分（Trajectory Scoring）             │
│    • 九维客观指标评分                                          │
│    • 基于规则的确定性评估                                      │
│    • 工具调用轨迹分析                                          │
└─────────────────────────────────────────────────────────────┘
```

### 15.2 Layer 1: 九维轨迹评分

**文件位置**: `supply_chain_agent/evaluation/trajectory_scorer.py`

客观评估Agent执行轨迹，9个维度均为确定性规则评分：

| 维度 | 满分 | 评估规则 |
|------|------|----------|
| **tool_selection** | 10 | 正确工具选择比例 |
| **params_complete** | 10 | 必需参数完整度 |
| **params_valid** | 10 | 参数值有效性 |
| **execution_order** | 10 | 工具调用顺序正确性 |
| **audit_compliance** | 10 | 审计规则合规性 |
| **answer_reachability** | 10 | 最终答案可达性 |
| **error_recovery** | 10 | 错误恢复成功率 |
| **clarification_efficiency** | 10 | 澄清效率（最少澄清次数） |
| **latency** | 10 | 响应延迟评分 |

**评分实现**：

```python
class TrajectoryScorer:
    """九维轨迹评分器"""

    def score(self, trajectory: Trajectory) -> TrajectoryScore:
        """
        计算九维评分

        每个维度独立评分，最终计算加权总分
        """
        scores = {
            "tool_selection": self._score_tool_selection(trajectory),
            "params_complete": self._score_params_complete(trajectory),
            "params_valid": self._score_params_valid(trajectory),
            "execution_order": self._score_execution_order(trajectory),
            "audit_compliance": self._score_audit_compliance(trajectory),
            "answer_reachability": self._score_answer_reachability(trajectory),
            "error_recovery": self._score_error_recovery(trajectory),
            "clarification_efficiency": self._score_clarification_efficiency(trajectory),
            "latency": self._score_latency(trajectory),
        }
        total = sum(scores.values()) / len(scores)
        return TrajectoryScore(dimensions=scores, total=total)
```

### 15.3 Layer 2: LLM Judge质量评分

**文件位置**: `supply_chain_agent/evaluation/quality_scorer.py`

使用LLM评估主观质量维度：

| 维度 | 满分 | 评估内容 |
|------|------|----------|
| **helpfulness** | 10 | 回答对用户有帮助程度 |
| **clarity** | 10 | 回答清晰度、结构化程度 |
| **faithfulness** | 10 | 回答对工具结果的忠实度 |

**Prompt模板**：

```python
QUALITY_EVAL_PROMPT = """你是一个客观的评估专家。请评估以下Agent回答的质量。

## 用户问题
{question}

## Agent回答
{answer}

## 工具结果
{tool_results}

## 评估标准
1. **helpfulness (有帮助程度)**: 回答是否解决了用户问题？
   - 10分: 完全解决，信息准确完整
   - 7分: 基本解决，有少量遗漏
   - 4分: 部分解决，有明显不足
   - 1分: 未解决问题

2. **clarity (清晰度)**: 回答是否清晰易懂？
   - 10分: 结构清晰，表述精准
   - 7分: 基本清晰，可优化
   - 4分: 有些混乱
   - 1分: 难以理解

3. **faithfulness (忠实度)**: 回答是否基于工具结果？
   - 10分: 完全基于事实，无幻觉
   - 7分: 基本基于事实，有合理推断
   - 4分: 有少量幻觉
   - 1分: 严重幻觉

## 输出格式
输出JSON: {"helpfulness": <1-10>, "clarity": <1-10>, "faithfulness": <1-10>}
"""
```

**LLM配置接口**：

```python
class QualityScorer:
    """LLM Judge质量评分器"""

    def __init__(self, llm_client: Optional[LLMClient] = None):
        """
        初始化质量评分器

        Args:
            llm_client: LLM客户端，默认使用GLM-4.7-flash
        """
        self.llm = llm_client or self._get_default_llm()

    def _get_default_llm(self) -> LLMClient:
        """获取默认LLM客户端（GLM-4.7-flash）"""
        from supply_chain_agent.agents.llm_client import get_llm_client
        return get_llm_client()
```

### 15.4 Layer 3: Cohen's Kappa校准

**文件位置**: `supply_chain_agent/evaluation/kappa_calibration.py`

使用Cohen's Kappa系数验证人机评估一致性：

```python
class KappaCalibrator:
    """Cohen's Kappa校准器"""

    def calculate_kappa(
        self,
        human_scores: List[int],
        llm_scores: List[int]
    ) -> KappaResult:
        """
        计算Cohen's Kappa系数

        Kappa值解释：
        - > 0.8: 优秀一致性
        - 0.6-0.8: 良好一致性
        - 0.4-0.6: 中等一致性
        - < 0.4: 需要校准
        """
        from sklearn.metrics import cohen_kappa_score
        kappa = cohen_kappa_score(human_scores, llm_scores)
        return KappaResult(
            kappa=kappa,
            interpretation=self._interpret_kappa(kappa),
            needs_calibration=kappa < 0.6
        )

    def calibrate_with_golden_samples(
        self,
        golden_samples: List[GoldenSample]
    ) -> CalibrationResult:
        """
        使用Golden Samples进行校准

        1. 运行LLM评估Golden Samples
        2. 对比人类专家评分
        3. 计算Kappa系数
        4. 如果<0.6，提示需要调整Prompt
        """
```

### 15.5 Golden Samples数据集

**文件位置**: `supply_chain_agent/evaluation/datasets/golden/samples.json`

包含30个标准评估样本，覆盖所有核心场景：

| 场景 | 样本数 | 覆盖内容 |
|------|--------|----------|
| 订单查询 | 5 | 订单号提取、订单详情、物流关联 |
| 物流查询 | 4 | 物流轨迹、配送状态 |
| 客户查询 | 4 | 客户信息、订单历史、统计数据 |
| 工单创建 | 5 | 各类型工单创建、参数验证 |
| 审批工单 | 6 | 审批流程、风险分析、用户确认 |
| 异常上报 | 4 | 异常类型识别、紧急程度 |
| 边缘场景 | 2 | 模糊输入、参数缺失 |

**Golden Sample结构**：

```json
{
  "id": "GS-001",
  "scenario": "order_query",
  "input": "查询订单77202的状态",
  "expected_intent": {
    "intent_level_1": "信息查询",
    "intent_level_2": "订单查询"
  },
  "expected_entities": {
    "order_id": "77202"
  },
  "expected_tools": ["query_order"],
  "expected_answer_patterns": ["订单状态", "配送状态"],
  "human_quality_scores": {
    "helpfulness": 10,
    "clarity": 9,
    "faithfulness": 10
  }
}
```

### 15.6 Layer 4: Harness集成

**文件位置**: `supply_chain_agent/evaluation/harness_integration.py`

复用现有Harness Engineering模块：

```python
class HarnessRulesIntegration:
    """集成Harness业务规则评估"""

    def __init__(self):
        from supply_chain_agent.harness.rules.evaluator import RuleEvaluator
        self.evaluator = RuleEvaluator()

    def evaluate_trajectory(self, trajectory: Trajectory) -> Dict:
        """使用Harness规则评估轨迹"""
        return self.evaluator.evaluate(trajectory.to_dict())


class HarnessEvalsIntegration:
    """集成Harness Evals评估器"""

    def __init__(self):
        from supply_chain_agent.harness.evals import (
            IntentAccuracyEvaluator,
            ToolCallAccuracyEvaluator,
            E2EWorkflowEvaluator
        )
        self.intent_eval = IntentAccuracyEvaluator()
        self.tool_eval = ToolCallAccuracyEvaluator()
        self.e2e_eval = E2EWorkflowEvaluator()

    def evaluate(self, trajectory: Trajectory) -> Dict:
        """运行所有Harness评估器"""
        return {
            "intent_accuracy": self.intent_eval.evaluate(trajectory),
            "tool_accuracy": self.tool_eval.evaluate(trajectory),
            "e2e_workflow": self.e2e_eval.evaluate(trajectory)
        }


class HarnessErrorClusterIntegration:
    """集成Harness错误聚类"""

    def __init__(self):
        from supply_chain_agent.harness.feedback.cluster_errors import cluster_errors
        self.cluster_errors = cluster_errors

    def analyze_errors(self, trajectories: List[Trajectory]) -> Dict:
        """分析轨迹中的错误模式"""
        return self.cluster_errors(trajectories)
```

### 15.7 数据集管理

**文件位置**: `supply_chain_agent/evaluation/datasets/dataset_manager.py`

```python
class DatasetManager:
    """评估数据集管理器"""

    def load_golden_samples(self) -> List[GoldenSample]:
        """加载Golden Samples"""
        with open("golden/samples.json") as f:
            return [GoldenSample(**s) for s in json.load(f)]

    def load_evaluation_set(self, name: str) -> List[Dict]:
        """加载指定评估集"""
        return self._load_json(f"evaluation_sets/{name}.json")

    def save_results(self, results: EvalResults, name: str):
        """保存评估结果"""
        path = f"results/{name}_{datetime.now():%Y%m%d_%H%M%S}.json"
        with open(path, 'w') as f:
            json.dump(results.to_dict(), f, indent=2)
```

### 15.8 监控与告警

**文件位置**: `supply_chain_agent/evaluation/monitoring/`

#### Prometheus指标导出

```python
# metrics_exporter.py
EVAL_RUN_COUNT = Counter(
    'agent_eval_run_total',
    '评估运行总次数',
    ['evaluator_type']
)

TRAJECTORY_SCORE = Histogram(
    'agent_trajectory_score',
    '轨迹评分分布',
    ['dimension'],
    buckets=[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
)

QUALITY_SCORE = Histogram(
    'agent_quality_score',
    '质量评分分布',
    ['dimension'],
    buckets=[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
)

KAPPA_SCORE = Gauge(
    'agent_eval_kappa_score',
    'Kappa一致性系数'
)
```

#### API端点

| 端点 | 方法 | 功能 |
|------|------|------|
| `/metrics` | GET | Prometheus指标（含评估指标） |
| `/eval/dashboard` | GET | 评估仪表盘数据 |
| `/eval/metrics` | GET | 评估指标详情 |
| `/eval/alerts` | GET | 评估告警列表 |

#### 告警规则

```python
# alert_manager.py
ALERT_RULES = [
    {
        "name": "low_trajectory_score",
        "condition": "avg_trajectory_score < 7.0",
        "severity": "warning",
        "message": "平均轨迹评分低于7.0，需要优化"
    },
    {
        "name": "low_kappa",
        "condition": "kappa_score < 0.6",
        "severity": "critical",
        "message": "Kappa一致性低于0.6，需要校准LLM Judge"
    },
    {
        "name": "high_error_rate",
        "condition": "error_rate > 0.1",
        "severity": "warning",
        "message": "评估错误率超过10%"
    }
]
```

### 15.9 环境变量配置

```bash
# Agent评估系统配置（V2.8新增）
EVAL_ENABLED=true                      # 启用评估系统
EVAL_LLM_PROVIDER=zhipu                # LLM Judge提供商
EVAL_LLM_MODEL=glm-4.7-flash           # LLM Judge模型
EVAL_KAPPA_THRESHOLD=0.6               # Kappa校准阈值
EVAL_GOLDEN_SAMPLES_PATH=./evaluation/datasets/golden/samples.json
EVAL_RESULTS_PATH=./evaluation/results/
```

### 15.10 使用示例

```python
from supply_chain_agent.evaluation import EvalRunner

# 创建评估运行器
runner = EvalRunner()

# 运行完整评估
results = await runner.run_full_evaluation(
    trajectory=my_trajectory,
    run_kappa_calibration=True
)

# 查看结果
print(f"轨迹总分: {results.trajectory_score.total:.2f}")
print(f"质量评分: {results.quality_score.total:.2f}")
print(f"Kappa系数: {results.kappa_result.kappa:.3f}")

# 检查是否需要校准
if results.kappa_result.needs_calibration:
    print("警告: LLM Judge需要校准!")
```

### 15.11 评估报告

评估完成后自动生成Markdown格式报告：

```markdown
# Agent评估报告

**评估时间**: 2026-06-08 12:00:00
**样本数量**: 30

## 轨迹评分

| 维度 | 平均分 | 标准差 |
|------|--------|--------|
| tool_selection | 9.2 | 0.8 |
| params_complete | 8.5 | 1.2 |
| params_valid | 9.0 | 0.9 |
| ... | ... | ... |
| **总分** | **8.7** | 0.6 |

## 质量评分

| 维度 | 平均分 | Kappa系数 |
|------|--------|-----------|
| helpfulness | 8.5 | 0.82 |
| clarity | 8.8 | 0.79 |
| faithfulness | 9.1 | 0.85 |

## 改进建议

1. params_complete维度得分较低，建议优化实体提取逻辑
2. clarification_efficiency有提升空间，可减少澄清轮次
```

---

## 16. 未来扩展建议

### 16.1 功能扩展

1. **更多意图支持**: 扩展更多业务场景的意图识别
2. **多语言支持**: 支持英文等其他语言的意图识别
3. **语音输入**: 集成语音识别，支持语音交互
4. **批量处理**: 支持批量工单处理

### 16.2 技术优化

1. **流式响应**: 支持LLM流式输出，降低首字延迟
2. **缓存优化**: 增加意图识别缓存，提升响应速度
3. **分布式部署**: 支持Kubernetes分布式部署
4. **监控增强**: 已集成Prometheus/Grafana监控（V2.7 Harness）

### 16.3 企业集成

1. **扩展业务数据**: 在 `dataset/BusinessData/` 添加更多业务数据文件
2. **扩展 SOP 文档**: 在 `dataset/SOPData/` 添加更多 SOP 文档
3. **OA系统集成**: 集成企业OA审批流程
4. **认证授权**: 增加企业级认证授权

### 16.4 Harness Engineering 增强

1. **业务规则扩展**: 根据业务需求添加更多审计规则
2. **Evals场景覆盖**: 扩展更多核心场景的自动化评估
3. **告警集成**: 集成邮件/钉钉/企微告警通知
4. **Dashboard可视化**: 开发Grafana Dashboard可视化监控

---

## 附录

### A. 关键文件清单

| 文件 | 行数 | 描述 |
|------|------|------|
| orchestrator.py | ~650 | 总控Agent |
| parser.py | ~835 | 解析师Agent |
| executor.py | ~1200 | 调度员Agent（V2.6新增审批分析功能） |
| auditor.py | ~334 | 审计员Agent |
| workflow.py | ~1050 | LangGraph工作流 |
| vector_store.py | ~666 | 记忆系统 |
| app.py | ~1100 | FastAPI应用（V2.8新增评估端点） |
| supply_chain_db.py | ~1426 | 数据库操作 |
| server.py | ~754 | MCP服务器 |
| client.py | ~490 | 工具客户端 |
| bert_ner.py | ~330 | BERT NER模块 |
| state.py | ~240 | 状态定义（V2.6新增approval_analysis） |
| report_generator.py | ~550 | 报告生成器（V2.6新增审批分析展示） |
| execution_plan.py | ~180 | Prompt模板（V2.6新增审批分析模板） |
| **harness/rules/loader.py** | ~150 | 规则加载器（V2.7新增） |
| **harness/rules/evaluator.py** | ~180 | 规则评估引擎（V2.7新增） |
| **harness/observability/metrics.py** | ~120 | Prometheus指标（V2.7新增） |
| **harness/observability/trace.py** | ~190 | Trace收集器（V2.7新增） |
| **harness/evals/base.py** | ~130 | 基础评估器（V2.7新增） |
| **harness/feedback/cluster_errors.py** | ~230 | 错误聚类（V2.7新增） |
| **evaluation/trajectory_scorer.py** | ~350 | 九维轨迹评分（V2.8新增） |
| **evaluation/quality_scorer.py** | ~280 | LLM Judge质量评分（V2.8新增） |
| **evaluation/kappa_calibration.py** | ~200 | Cohen's Kappa校准（V2.8新增） |
| **evaluation/harness_integration.py** | ~250 | Harness集成（V2.8新增） |
| **evaluation/datasets/dataset_manager.py** | ~150 | 数据集管理（V2.8新增） |
| **evaluation/monitoring/metrics_exporter.py** | ~180 | Prometheus指标导出（V2.8新增） |
| **evaluation/monitoring/alert_manager.py** | ~120 | 告警管理（V2.8新增） |
| **evaluation/monitoring/dashboard.py** | ~200 | 仪表盘数据（V2.8新增） |

### B. 依赖清单

**核心依赖**:
- langgraph>=0.2.0
- langchain>=0.2.0
- fastapi>=0.110.0
- fastmcp>=0.1.0
- chromadb>=0.5.0
- pydantic>=2.0.0
- transformers>=5.9.0
- torch>=2.8.0
- **prometheus-client>=0.17.0** (V2.7新增)
- **watchdog>=3.0.0** (V2.7新增)
- **scikit-learn>=1.0.0** (V2.8新增，用于Kappa计算)

**前端依赖**:
- react@18.2.0
- antd@5.12.0
- typescript@5.3.0
- vite@5.0.0

### C. 环境变量

```bash
# LLM配置
SCA_LLM_PROVIDER=zhipu
SCA_LLM_MODEL=glm-4.7
SCA_LLM_API_KEY=your-api-key

# 系统配置
SCA_MAX_RETRIES=3
SCA_CLARIFICATION_MAX_ATTEMPTS=3

# 存储配置
SCA_VECTOR_STORE_PATH=./supply_chain_agent/data/vector_store
SCA_SQLITE_DB_PATH=./supply_chain_agent/data/agent_memory.db

# Harness Engineering配置（V2.7新增）
HARNESS_RULES_ENABLED=true           # 启用业务规则审计
HARNESS_STRUCTURED_LOGS=true         # 结构化日志
HARNESS_METRICS_ENABLED=true         # Prometheus Metrics
HARNESS_TRACE_ENABLED=true           # Trace收集
HARNESS_TRACE_SAMPLE_RATE=0.01       # Trace采样率
HARNESS_EVALS_LEVEL=1                # Evals评估等级
HARNESS_PRE_CHECK=false              # 参数预检装饰器

# Agent评估系统配置（V2.8新增）
EVAL_ENABLED=true                    # 启用评估系统
EVAL_LLM_PROVIDER=zhipu              # LLM Judge提供商
EVAL_LLM_MODEL=glm-4.7-flash         # LLM Judge模型
EVAL_KAPPA_THRESHOLD=0.6             # Kappa校准阈值
EVAL_GOLDEN_SAMPLES_PATH=./evaluation/datasets/golden/samples.json
EVAL_RESULTS_PATH=./evaluation/results/

# 数据初始化
# 首次运行需要初始化数据:
# python -m supply_chain_agent.data.init_data
```

---

**报告生成完成**

本报告基于对项目所有源代码和文档的全面分析生成，涵盖了项目的各个方面，包括架构设计、核心模块、技术栈、工作流程、记忆系统、工具集成、前端界面、测试评估、配置部署、Harness Engineering工程化能力、Agent评估系统等。读者通过此文档即可全面了解本项目，而无需再打开代码研究。
