# Supply Chain Agent - 智能供应链工单处理Agent系统

[![License](https://img.shields.io/badge/License-MIT-blue.svg)](./LICENSE)
[![Python](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://www.python.org/)
[![Documentation](https://img.shields.io/badge/docs-中文文档-green.svg)](./docs/)
[![Architecture](https://img.shields.io/badge/Architecture-Multi--Agent-blue.svg)](#)


基于LangGraph框架构建的智能供应链工单处理Agent系统。本项目将多智能体协作技术应用于供应链运营场景，通过四Agent星型拓扑架构协同工作，为企业提供智能化的工单处理能力。
> 技术栈：Python · LangChain · LangGraph · FastAPI · React · ChromaDB · SQLite

An intelligent agent system for supply chain work order processing built on the LangGraph framework. This project applies multi-agent collaboration technology to supply chain operations, enabling four agents to work together in a star topology architecture, delivering intelligent work order processing capabilities for enterprises.
> Tech Stack: Python · LangChain · LangGraph · FastAPI · React · ChromaDB · SQLite

---
> **更新记录** [持续更新中]
>
> 2026-05-13: 初始版本发布
>
> 2026-05-23: 重构数据架构，真实数据库交互替代Mock数据响应
>
> 2026-05-24: 更新MCP工具，优化Executor Agent工具调用；优化意图识别实体提取
>
> 2026-05-28: 重构意图识别分层体系；优化响应卡片
>
> 2026-06-01: 优化审批工单意图下，工具调用的规划与执行方案
>
> 2026-06-03: 架构优化：创建完整异常层次结构；明确Orchestrator职责边界，剥离Workflow类等
>
> 2026-06-04: skill加载方案实现审批工单意图下的工具调用规划；前端优化
>
> 2026-06-07: 审批工单场景优化：LLM分析推荐+用户确认审批
>
> 2026-06-07: Harness Engineering工程化能力：三层增强模型（配置化约束、可观测性、反馈改进）
>

---

> 🎯 **项目定位**: L3级自主Agent系统，为供应链运营团队提供协作副驾驶能力
>
> 💡 **核心理念**: 基于LangGraph多智能体协作，实现意图识别、工具调用、结果审计的完整工单处理流程
>
> 🏭 **应用场景**: 供应链运营专员工单处理、跨系统查询、异常上报、审批流转

## 🎯 项目背景与价值

### 📊 供应链运营痛点分析

传统供应链工单处理面临诸多挑战：

- **📝 意图识别困难**: 用户输入多样化，准确理解成本高
- **🔄 跨系统查询复杂**: 需要在多个系统间切换，效率低下
- **⚠️ 异常处理繁琐**: 异常上报流程长，响应不及时
- **✅ 审批流转低效**: 人工审批周期长，缺乏标准化流程
- **🧠 经验依赖性强**: 过度依赖专家经验，难以规模化复制

### 💡 AI智能体解决方案

本系统通过四Agent星型拓扑架构，模拟供应链运营团队的协作决策过程：

- **🎯 总控Agent (Orchestrator)**: 全局状态管理、上下文窗口管理、子Agent调度
- **🔍 解析师Agent (Parser)**: 意图识别、实体提取、槽位填充
- **⚙️ 调度员Agent (Executor)**: 工具编排、并发控制、结果收集
- **🛡️ 审计员Agent (Auditor)**: 结果验证、风控拦截、一致性检查

### 🚀 核心价值主张

- **⚡ 处理效率提升**: 自动化工单处理，响应时间从分钟级缩短到秒级
- **🎯 意图识别准确**: 规则+LLM融合识别，准确率达72%
- **🔄 标准化流程**: 建立可复制的工单处理标准和流程
- **🛡️ 风险可控**: 内置熔断器保护和审计机制
- **📊 数据驱动**: 基于SOP知识库的智能决策

## 🏗️ 项目结构

```
Supply-Chain-Agent/
├── supply_chain_agent/           # 主模块
│   ├── common/                   # 公共模块
│   │   ├── exceptions.py         # 异常层次结构
│   │   ├── service_container.py  # 服务容器（依赖注入）
│   │   ├── protocols.py          # 消息协议定义
│   │   ├── param_validator.py    # 参数验证器
│   │   └── valid_values.py       # 有效值定义
│   ├── agents/                   # Agent定义
│   │   ├── orchestrator.py       # 总控Agent
│   │   ├── parser.py             # 解析师Agent
│   │   ├── executor.py           # 调度员Agent
│   │   └── auditor.py            # 审计员Agent
│   ├── tools/                    # MCP工具实现
│   │   ├── server.py             # MCP服务器
│   │   └── client.py             # 工具客户端
│   ├── graph/                    # LangGraph工作流
│   │   ├── state.py              # 全局状态定义
│   │   └── workflow.py           # 节点与边逻辑
│   ├── memory/                   # 记忆系统
│   │   ├── vector_store.py       # 向量存储管理
│   │   ├── checkpoint.py         # 检查点管理
│   │   └── knowledge_retriever.py# 知识检索器
│   ├── prompts/                  # Prompt模板
│   ├── nlp/                    # NLP模块
│   │   └── bert_ner.py         # BERT实体识别
│   ├── harness/                  # Harness Engineering工程化模块
│   │   ├── rules/                # Layer 1: 业务规则
│   │   │   ├── loader.py         # YAML规则加载器
│   │   │   ├── evaluator.py      # 规则评估引擎
│   │   │   └── business_rules.yaml
│   │   ├── observability/        # Layer 2: 可观测性
│   │   │   ├── metrics.py        # Prometheus指标
│   │   │   ├── logging_config.py # 结构化日志
│   │   │   └── trace.py          # Trace收集器
│   │   ├── evals/                # Layer 2: Evals评估
│   │   │   ├── base.py           # 基础评估器
│   │   │   ├── intent_eval.py    # 意图评估器
│   │   │   ├── tool_eval.py      # 工具评估器
│   │   │   └── e2e_eval.py       # 端到端评估器
│   │   ├── feedback/             # Layer 3: 反馈改进
│   │   │   ├── cluster_errors.py # 错误聚类
│   │   │   └── weekly_report.py  # 周度报告
│   │   ├── spec/                 # SPEC规范文件
│   │   └── playbook.md           # Harness运维手册
│   ├── data/                     # Python数据模块
│   │   ├── supply_chain.db       # 业务数据库(运行时)
│   │   ├── agent_memory.db       # 记忆数据库(运行时)
│   │   ├── vector_store/         # 向量存储(运行时)
│   │   ├── supply_chain_db.py    # 数据库操作
│   │   └── data_loader.py        # 数据加载器
│   ├── models/                   # 模型文件
│   │   └── bert-chinese-wwm/     # BERT中文预训练模型
│   ├── frontend/                 # React前端
│   ├── app.py                    # FastAPI应用
│   ├── run.py                    # 运行脚本
│   ├── config.py                 # 配置管理
│   └── AGENTS.md                 # 系统入口指南
├── dataset/                      # 数据源目录
│   ├── BusinessData/             # 业务数据(CSV)
│   ├── SOPData/                  # SOP文档(Markdown)
│   ├── OtherData/                # 配置文件
│   └── README.md                 # 数据说明
├── docs/                         # 项目文档
│   ├── PROJECT_RESEARCH_REPORT.md # 项目研究报告
│   └── Harness Engineering Design.md # Harness设计文档
├── requirements.txt              # Python依赖
└── README.md                     # 本文件
```

## 🏗️ 技术架构亮点

### 🤖 四Agent星型拓扑架构

基于 **LangGraph** 构建的多智能体工作流：

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

**核心设计原则**:
- **🎯 职责分离**: 每个Agent专注单一职责，便于维护和扩展
- **🔄 协作决策**: 模拟真实团队协作流程
- **🛡️ 审计保障**: 执行结果必须经过审计验证
- **👤 Human-in-the-loop**: 关键操作支持人工确认

### 🔧 技术栈选型

### 🧠 LLM与NLP

| 技术领域 | 选型方案 | 选择理由 |
|---------|---------|---------|
| **🧠 Agent框架** | LangGraph + LangChain | 成熟的多智能体编排和状态管理 |
| **🌐 API服务** | FastAPI + Uvicorn | 高性能异步API框架，支持REST和WebSocket |
| **🖥️ 前端** | React 18 + TypeScript + Ant Design 5 | 企业级UI组件库 |
| **🤖 LLM** | 智谱GLM-4.7（可配置） | 国产大模型，成本可控，支持工具调用 |
| **📝 NER** | BERT-base-chinese-wwm | 中文实体识别，准确率高 |
| **📚 向量存储** | ChromaDB | 轻量级向量数据库 |
| **💾 关系存储** | SQLite | 轻量级关系数据库 |

### 🧠 三层记忆系统

```
┌─────────────────────────────────────────────────────────────┐
│                    短期记忆 (Short-term)                     │
│  • 滑动窗口存储最近20条对话                                  │
│  • 支持摘要压缩防止Token溢出                                 │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    工作记忆 (Working)                        │
│  • LangGraph共享状态 (AgentState)                           │
│  • 支持检查点持久化                                          │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    长期记忆 (Long-term)                      │
│  • ChromaDB: SOP手册、FAQ知识库                              │
│  • SQLite: 工单记录、操作日志、统计数据                      │
└─────────────────────────────────────────────────────────────┘
```

## ✨ 功能特性

### 🎯 核心功能

- **🔍 三层意图识别**: 规则引擎(意图匹配) → BERT NER(实体提取) → LLM(兜底补充)，职责分离清晰
- **📝 BERT实体识别**: 集成bert-base-chinese-wwm模型，准确提取订单号、客户ID、工单号、产品卡ID等实体
- **🔄 跨系统查询**: 11个MCP工具调用，支持订单、物流、客户、产品、工单查询与操作
- **📋 工单管理**: 创建质量检验、审批等工单，支持工单查询和审批流转
- **⚠️ 异常上报**: 智能异常分类和上报流程，支持紧急程度设置
- **✅ 审批确认**: 支持审批操作，危险操作需二次确认

### 🌐 Web管理界面

- **💬 对话界面**: 自然语言交互，实时响应展示
- **📊 仪表盘**: 性能指标可视化展示
- **🔧 工具管理**: MCP工具状态监控
- **⚙️ 系统配置**: 灵活的参数配置

### 🛡️ 可靠性保障

- **⚡ 熔断器保护**: 防止工具故障级联扩散
- **🔄 智能重试**: 多种重试策略（固定延迟、指数退避、自适应）
- **📉 降级响应**: 工具不可用时，知识库检索+LLM生成友好提示
- **✅ 审计验证**: 执行结果必须经过审计Agent验证

### 🔧 Harness Engineering 工程化能力

系统内置三层工程化增强能力，所有特性通过环境变量独立开关：

| 层级 | 能力 | 说明 |
|------|------|------|
| **Layer 1** | 配置化约束 | 业务规则YAML配置、参数预检装饰器 |
| **Layer 2** | 验证与可观测 | Prometheus Metrics、结构化日志、Trace收集、Evals评估 |
| **Layer 3** | 反馈与改进 | 错误聚类分析、周度报告生成 |

**核心特性**：
- **📊 Prometheus Metrics**: 9个标准指标，`/metrics`端点暴露
- **📝 结构化日志**: JSON格式输出，便于ELK/Loki采集
- **🔍 Trace收集**: 采样率控制+错误全量记录
- **✅ Evals评估**: 9个评估器覆盖意图、工具、审计、端到端场景

详见 [Harness Playbook](./supply_chain_agent/harness/playbook.md)

## 🚀 快速开始

### 环境要求

- Python 3.9+ (推荐 3.10+)
- Node.js 18+ (仅前端需要)
- 4GB+ RAM (推荐 8GB+)

### 安装部署

```bash
# 1. 克隆项目
git clone https://github.com/ZeynXu/Supply-Chain-Agent.git
cd Supply-Chain-Agent

# 2. 创建虚拟环境
python -m venv env
source env/bin/activate  # Linux/macOS
# env\Scripts\activate  # Windows

# 3. 安装后端依赖
pip install -r requirements.txt

# 4. 配置环境变量
# 编辑 .env 文件，配置API密钥

# 5. 启动后端
python -m supply_chain_agent --mode web --port 8000

# 6. 启动前端（另开终端）
cd supply_chain_agent/frontend
npm run dev
```

### 配置指南

#### 必需配置

编辑 `.env` 文件：

```bash
# 智谱AI API Key (推荐)
SCA_LLM_PROVIDER=zhipu
SCA_LLM_MODEL=glm-4.7
SCA_LLM_API_KEY=your_zhipu_api_key

# 或 OpenAI兼容API
SCA_LLM_PROVIDER=openai
SCA_LLM_API_KEY=your_openai_api_key
```

#### 可选配置

```bash
# 记忆系统配置
SCA_MEMORY_WINDOW_SIZE=20
SCA_VECTOR_STORE_PATH=./supply_chain_agent/data/vector_store
SCA_SQLITE_DB_PATH=./supply_chain_agent/data/agent_memory.db

# 熔断器配置
SCA_CIRCUIT_BREAKER_FAILURES=3
SCA_CIRCUIT_BREAKER_RESET_TIMEOUT=300

# Harness Engineering配置（工程化能力开关）
HARNESS_RULES_ENABLED=true           # 业务规则审计
HARNESS_STRUCTURED_LOGS=true         # 结构化日志
HARNESS_METRICS_ENABLED=true         # Prometheus Metrics
HARNESS_TRACE_ENABLED=true           # Trace收集
HARNESS_TRACE_SAMPLE_RATE=0.01       # Trace采样率
HARNESS_EVALS_LEVEL=1                # Evals评估等级(0=禁用,1=门禁,2=告警)
```

### 访问地址

| 服务 | 地址 | 说明 |
|------|------|------|
| React前端 | http://localhost:3000 | 主要交互界面 |
| FastAPI后端 | http://localhost:8000 | REST API服务 |
| Prometheus Metrics | http://localhost:8000/metrics | 监控指标 |
| API文档 | http://localhost:8000/api/docs | Swagger文档 |

### 使用示例

#### API调用

```bash
# 通过Agent处理用户输入（推荐）
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "订单77202的物流到哪了"}'

# 查询订单（直接调用MCP工具）
curl -X POST http://localhost:8000/api/tools/query_order \
  -H "Content-Type: application/json" \
  -d '{"order_id": "77202"}'

# 查询物流
curl -X POST http://localhost:8000/api/tools/query_shipment \
  -H "Content-Type: application/json" \
  -d '{"order_id": "77202"}'

# 创建工单
curl -X POST http://localhost:8000/api/tools/create_work_order \
  -H "Content-Type: application/json" \
  -d '{"work_type": "质检", "description": "订单77202质量检验", "order_id": "77202"}'

# 查看系统状态
curl -X GET http://localhost:8000/api/status

# 查看可用工具
curl -X GET http://localhost:8000/api/tools
```

#### Python SDK

```python
import asyncio
from supply_chain_agent.agents.orchestrator import OrchestratorAgent

async def main():
    agent = OrchestratorAgent()
    # 物流查询
    result = await agent.process("订单77202的物流到哪了")
    print(result["response"])

    # 创建工单
    result = await agent.process("创建质检工单，订单77202")
    print(result["response"])

asyncio.run(main())
```

#### 数据库直接查询

```python
from supply_chain_agent.data.supply_chain_db import get_order_by_id, get_customer_by_id

# 查询订单
order = get_order_by_id("77202")
print(f"订单状态: {order['order_status']}, 配送状态: {order['delivery_status']}")

# 查询客户
customer = get_customer_by_id(20755)
print(f"客户: {customer['customer_fname']} {customer['customer_lname']}")
```

## 📊 支持的意图

### 任务分类体系

**一级任务分类**：

| 一级任务 | 描述 | 包含二级任务 |
|----------|------|--------------|
| **信息查询** | 查询客户、订单、产品、物流等信息 | 客户查询、订单查询、产品查询、物流查询、工单查询、客户统计 |
| **工单管理** | 创建和审批工单 | 创建工单、审批工单 |
| **异常上报** | 上报供应链过程中的问题 | 异常上报 |

**二级任务与MCP工具映射**：

| 二级任务 | 调用工具 | 必需参数 | 可选参数 |
|----------|----------|----------|----------|
| **客户查询** | query_customer | customer_id | - |
| **客户订单查询** | query_customer_orders | customer_id | - |
| **订单查询** | query_order | order_id | - |
| **订单明细查询** | query_order_items | order_id | - |
| **产品查询** | query_product | product_card_id | - |
| **物流查询** | query_shipment | order_id | - |
| **客户统计** | query_customer_statistics | customer_id | - |
| **工单查询** | query_work_order | work_order_id | - |
| **创建工单** | create_work_order | work_type, description | order_id, customer_id, priority |
| **审批工单** | approve_work_order | work_order_id | action, comment |
| **异常上报** | report_issue | issue_type, description | order_id, urgency |

### 使用示例

| 用户输入示例 | 识别意图 | 调用工具 |
|--------------|----------|----------|
| "查询订单77202的状态" | 信息查询→订单查询 | query_order |
| "订单77202的物流到哪了" | 信息查询→物流查询 | query_shipment |
| "订单77202有哪些商品" | 信息查询→订单明细查询 | query_order_items |
| "客户20755的信息" | 信息查询→客户查询 | query_customer |
| "客户20755的所有订单" | 信息查询→客户订单查询 | query_customer_orders |
| "客户20755的统计数据" | 信息查询→客户统计 | query_customer_statistics |
| "创建质检工单，订单77202" | 工单管理→创建工单 | create_work_order |
| "查询工单WO-2024-001" | 信息查询→工单查询 | query_work_order |
| "审批工单WO-2024-001通过" | 工单管理→审批工单 | approve_work_order |
| "报告订单75939物流延迟" | 异常上报 | report_issue |

## 📈 应用效果

### 性能指标

| 指标 | 目标值 | 实际值 | 状态 |
|------|--------|--------|------|
| **任务成功率** | > 65% | **72.0%** | ✅ 达标 |
| **平均响应时间** | < 3秒 | **2.10秒** | ✅ 达标 |
| **用户采纳率** | > 40% | **61.2%** | ✅ 达标 |
| **工具可用率** | > 95% | **96.0%** | ✅ 达标 |

### 🏭 典型应用场景

#### 案例一：订单查询
- **用户输入**: "查询订单77202的状态"
- **处理流程**: 意图识别→订单查询 → 实体提取(order_id=77202) → 调用query_order工具 → 审计验证 → 响应生成
- **输出结果**: "订单77202状态为COMPLETE，配送状态为Advance shipping"

#### 案例二：物流查询
- **用户输入**: "订单77202的物流到哪了"
- **处理流程**: 意图识别→物流查询 → 实体提取(order_id=77202) → 调用query_shipment工具 → 审计验证 → 响应生成
- **输出结果**: 物流轨迹信息和当前状态

#### 案例三：工单创建
- **用户输入**: "创建质检工单，订单77202需要检验"
- **处理流程**: 意图识别→创建工单 → 实体提取(work_type=质检, order_id=77202) → 调用create_work_order工具 → 审计验证 → 响应生成
- **输出结果**: "已创建质检工单WO-2026-XXX，关联订单77202"

#### 案例四：异常上报
- **用户输入**: "报告订单75939物流延迟问题"
- **处理流程**: 意图识别→异常上报 → 实体提取(issue_type=物流延迟, order_id=75939) → 调用report_issue工具 → 响应生成
- **输出结果**: "已上报物流延迟异常，工单号ISS-2026-XXX，已通知相关责任人"

## Skill 系统

Supply-Chain-Agent 使用 Skill 系统指导 LLM 完成特定任务。Skill 采用渐进式披露（Progressive Disclosure）的上下文工程技术。

### 审批工单 Skill

当检测到审批工单意图时，系统自动加载 `approval_workflow` skill：

- **位置**: `supply_chain_agent/skills/approval_workflow/`
- **触发条件**: `intent_level_2 = "审批工单"`
- **功能**: 指导 LLM 生成执行计划、提取参数、执行工具

### 审批工单分析流程（V2.6新增）

审批工单意图采用**LLM分析推荐+用户确认**模式：

**工作流程**：
1. **意图识别**：只需提供 `work_order_id`，无需提前指定审批动作
2. **工具链执行**：依次执行 `query_work_order` → `query_order` → `query_customer_statistics`
3. **规则参数提取**：工具间参数传递使用规则提取，无需LLM解析
4. **LLM分析**：查询完成后，LLM结合SOP文档进行风险分析和审批建议
5. **用户确认**：前端展示分析结果，用户决定审批动作（approve/reject/escalate）

**技术特点**：
- 规则参数提取：`_extract_params_for_next_tool()` 方法定义字段映射规则
- LLM分析优化：精简Prompt模板（~2000字符），提取关键字段减少token消耗
- 前端展示：显示LLM分析结果（风险等级、审批建议、置信度），而非原始查询数据

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
    """
```

**性能优化效果**：

| 模式 | thinking | max_tokens | 典型耗时 |
|------|----------|------------|----------|
| 普通模式 | 启用 | 65536 | ~35秒 |
| 快速模式 | 禁用 | 512-1024 | ~5秒 |

### 前端实时进度显示

前端 Agent 执行轨迹面板实时显示 Skill 加载过程：

- **实时事件流**: 使用 LangGraph `astream_events` API，节点进入时立即显示
- **Skill 卡片**: 与工具调用卡片风格一致，显示加载状态、耗时、结果
- **PendingSkills 机制**: 处理事件顺序问题，确保 Skill 正确关联到对应步骤

## 🏗️ 架构设计

### 📊 代码规模统计

| 模块 | 文件 | 代码行数 | 主要职责 |
|------|------|----------|----------|
| **Orchestrator** | orchestrator.py | ~400行 | 总控协调、依赖注入 |
| **Parser** | parser.py | ~1000行 | 意图识别、实体提取 |
| **Executor** | executor.py | ~1200行 | 工具编排、执行控制、审批分析（V2.6） |
| **Auditor** | auditor.py | ~350行 | 结果验证、风控审计 |
| **Workflow** | workflow.py | ~1800行 | 状态机、节点逻辑 |
| **Exceptions** | exceptions.py | ~200行 | 异常层次结构 |
| **ServiceContainer** | service_container.py | ~300行 | 服务容器（依赖注入） |
| **MCP Server** | server.py | ~750行 | 工具服务、数据查询 |
| **Database** | supply_chain_db.py | ~1400行 | 数据存储、业务查询 |
| **App** | app.py | ~1100行 | API服务、WebSocket |
| **总计** | - | **~8500行** | 核心业务代码 |

### 📋 设计原则

基于"**使用成熟技术架构专注业务场景创新**"的理念：

1. **🔧 技术选型**: 优先选择成熟、稳定的技术栈（LangGraph、LangChain）
2. **🎯 业务导向**: 技术服务于业务目标，不为技术而技术
3. **⚡ 快速迭代**: 支持快速验证和迭代优化
4. **🛡️ 风险可控**: 多层降级机制，确保系统稳定性
5. **📈 可扩展性**: 模块化设计，支持功能扩展

### 🤖 智能体设计

#### 核心智能体职责

1. **🎯 Orchestrator (总控Agent)**
   - 职责：依赖注入管理、高层API封装、响应处理、错误协调
   - 工作流控制逻辑已移至Workflow类
   - 核心方法：`process()`, `process_with_callback()`, `_extract_response()`
   - 输出：最终响应

2. **🔍 Parser (解析师Agent)** (~830行)
   - 职责：意图识别、实体提取、槽位填充
   - 三层意图识别有明确触发条件，实体提取方法分离
   - 核心方法：`parse_intent()`, `_extract_entities_by_rules()`, `_extract_entities_by_ner()`
   - 输出：结构化意图（primary_task, secondary_task, entities, slots）

3. **⚙️ Executor (调度员Agent)** (~1200行)
   - 职责：工具编排、并发控制、结果收集、审批分析（V2.6新增）
   - 能力：熔断保护、智能重试、规则参数提取、LLM审批分析
   - 核心方法：`execute_plan_with_llm_feedback()`, `execute_tool()`, `generate_approval_analysis()`（V2.6新增）
   - 输出：工具执行结果、审批分析报告

4. **🛡️ Auditor (审计员Agent)** (~334行)
   - 职责：结果验证、风控拦截、一致性检查
   - 能力：多维度审计规则（missing_tracking_number, unusual_delivery_time等）
   - 核心方法：`audit_results()`, `_check_single_result()`
   - 输出：审计报告（passed, issues, suggestions）

### 🔄 协作流程

**LangGraph 8节点状态机**：

| 节点 | 职责 | 输入 | 输出 |
|------|------|------|------|
| parse_input | 意图解析 | 用户输入 | 意图+实体 |
| clarify | 澄清确认 | 不完整意图 | 澄清问题 |
| plan_task | 任务规划 | 结构化意图 | 执行计划 |
| execute_task | 工具执行 | 执行计划 | 工具结果 |
| retry | 智能重试 | 失败结果 | 重试策略 |
| audit | 结果审计 | 执行结果 | 审计报告 |
| generate_report | 报告生成 | 审计结果 | 最终响应 |
| handle_error | 错误处理 | 错误信息 | 友好提示 |

```mermaid
graph TD
    A[用户输入] --> B[parse_input 解析]
    B --> C{需要澄清?}
    C -->|是| D[clarify 澄清]
    D --> B
    C -->|否| E[plan_task 规划]
    E --> F[execute_task 执行]
    F --> G{执行成功?}
    G -->|否| H[retry 重试]
    H --> F
    G -->|是| I[audit 审计]
    I --> J{审计通过?}
    J -->|否| K[handle_error 错误处理]
    J -->|是| L[generate_report 生成报告]
    L --> M[响应输出]
```

## 🎯 项目亮点

### 💡 技术创新点

1. **🤖 四Agent星型拓扑**
   - 总控Agent协调三个专业子Agent，职责清晰
   - Orchestrator职责明确，工作流控制逻辑移至Workflow类
   - 支持真正的依赖注入，通过ServiceContainer获取依赖

2. **🔄 LangGraph状态机**
   - 8节点状态机（parse_input → clarify → plan_task → execute_task → retry → audit → generate_report → handle_error）
   - 节点函数提取为类方法，便于独立测试和复用
   - 支持中断恢复和Human-in-the-loop
   - 检查点持久化，支持断点恢复

3. **🧠 三层记忆系统**
   - 短期+工作+长期记忆，支持RAG检索
   - SOP知识库增强，提升决策质量

4. **📝 三层意图识别架构**
   - 第一层：规则引擎专注意图模式匹配（一级+二级）+ 规则实体提取 + 置信度计算
   - 第二层：BERT NER专注实体提取（触发条件：置信度<0.75或实体为空）
   - 第三层：LLM兜底（触发条件：置信度<0.7或需要实体但无实体）
   - 明确的触发条件判断方法：`_can_skip_further_layers()`, `_should_trigger_ner()`, `_should_trigger_llm()`
   - 职责分离清晰，降低LLM调用成本

5. **🛡️ 异常处理层次结构**
   - 定义RecoverableError（可恢复）和UnrecoverableError（不可恢复）异常基类
   - 具体异常类型：IntentParseError, ToolExecutionError, ValidationError等
   - `wrap_exception()`自动包装标准异常
   - 支持智能错误恢复策略

6. **🔧 熔断器模式**
   - 工具调用熔断保护，防止故障扩散
   - 多种重试策略，智能降级

7. **📋 审批工单LLM分析推荐模式（V2.6新增）**
   - 用户只需提供工单号，无需提前指定审批动作
   - 工具链执行后，LLM结合SOP文档进行风险分析和审批建议
   - 规则参数提取替代LLM解析，降低token消耗
   - 前端展示分析结果（风险等级、审批建议），用户确认后执行
   - 实现智能化审批辅助决策

### 🚀 工程实践

1. **⚡ 三层意图识别**
   - 规则引擎优先：意图模式匹配 + 置信度计算（score基于关键词匹配）
   - BERT NER补充：实体提取，支持订单号、客户ID、产品卡ID、工单号等
   - LLM兜底：规则未命中/置信度低/实体为空时触发

2. **📉 知识库降级**
   - 工具不可用时，知识库检索+LLM生成友好提示
   - **不返回假数据**，明确标记data_available=False

3. **✅ 审批二次确认**
   - 危险操作（审批）必须用户二次确认
   - V2.6新增LLM分析推荐+用户确认模式，智能化审批辅助决策
   - 防止误操作风险

4. **📊 四维评估体系**
   - 效果、效率、体验、稳定性四维评估
   - 量化指标，持续优化

5. **🔗 MCP工具对齐**
   - 11个MCP工具完整实现，无虚构工具调用
   - 参数验证严格，可选参数按需传递

## 📂 数据说明

### 数据源目录

数据文件位于 `dataset/` 目录，详见 [dataset/README.md](./dataset/README.md)。

| 目录 | 内容 | 说明 |
|------|------|------|
| `dataset/BusinessData/` | 业务数据CSV | 供应链订单、客户、产品、物流数据 |
| `dataset/SOPData/` | SOP文档 | 供应链审批管理办法等Markdown文档 |
| `dataset/OtherData/` | 配置文件 | 实体映射、降级模板、Agent配置 |

### 运行时数据

运行时数据存储于 `supply_chain_agent/data/` 目录：

| 文件/目录 | 说明 |
|-----------|------|
| `supply_chain.db` | 业务数据库（客户、订单、产品等） |
| `agent_memory.db` | 记忆数据库（工单记录、工具统计） |
| `vector_store/` | ChromaDB向量存储（SOP文档嵌入） |

## 🤝 贡献指南

### 🌟 欢迎贡献

我们欢迎各种形式的贡献：

- 🐛 **Bug报告**: 发现问题，提交Issue
- ✨ **功能建议**: 提出新功能需求
- 📚 **文档改进**: 完善文档，提高可读性

### 📝 贡献流程

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建 Pull Request

## 📄 许可证

本项目基于 MIT 许可证开源。详见 [LICENSE](LICENSE) 文件。

## 📞 联系方式

- **GitHub Issues**: [提交问题和建议](https://github.com/ZeynXu/Supply-Chain-Agent/issues)
- **项目主页**: [详细介绍](https://github.com/ZeynXu/Supply-Chain-Agent)

## ⚠️ 免责声明

本系统仅用于决策支持，不构成最终业务决策建议。用户应结合实际业务情况，谨慎评估和使用系统输出结果。

---

<div align="center">

**🌟 如果这个项目对您有帮助，请给我们一个 Star！**

[⭐ Star this repo](https://github.com/ZeynXu/Supply-Chain-Agent) | [🍴 Fork this repo](https://github.com/ZeynXu/Supply-Chain-Agent/fork) | [📖 Read the docs](./docs/)

</div>
