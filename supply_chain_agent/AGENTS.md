# Supply-Chain-Agent 系统指南

本文档为 Supply-Chain-Agent 智能供应链工单处理系统的入口指南。

---

## 系统概述

Supply-Chain-Agent 是一个基于 LangGraph 的智能供应链工单处理系统，采用四 Agent 星型拓扑架构。

### 核心架构

```
                    ┌──────────────┐
                    │   Planner    │
                    │    Agent     │
                    └──────┬───────┘
                           │
         ┌─────────────────┼─────────────────┐
         │                 │                 │
         ▼                 ▼                 ▼
┌────────────────┐ ┌────────────────┐ ┌────────────────┐
│    Parser      │ │    Executor    │ │    Auditor     │
│    Agent       │ │    Agent       │ │    Agent       │
└────────────────┘ └────────────────┘ └────────────────┘
```

---

## Agent 职责

### Planner Agent (编排中心)
- **职责**: 意图识别、任务编排、流程控制
- **位置**: `supply_chain_agent/agents/planner.py`
- **输入**: 用户自然语言查询
- **输出**: 执行计划、最终响应

### Parser Agent (意图解析)
- **职责**: 解析用户意图、提取实体
- **位置**: `supply_chain_agent/agents/parser.py`
- **输入**: 用户查询文本
- **输出**: 意图分类、实体列表

### Executor Agent (工具执行)
- **职责**: 执行工具调用、获取数据
- **位置**: `supply_chain_agent/agents/executor.py`
- **输入**: 执行计划
- **输出**: 工具执行结果

### Auditor Agent (审计校验)
- **职责**: 业务规则校验、风险审计
- **位置**: `supply_chain_agent/agents/auditor.py`
- **输入**: 工具执行结果
- **输出**: 审计报告、风险提示

---

## 核心流程

### 1. 请求处理流程

```python
用户输入 → Planner Agent
           │
           ├──→ Parser Agent (意图解析)
           │
           ├──→ Executor Agent (工具执行)
           │         │
           │         └──→ MCP Tools
           │
           ├──→ Auditor Agent (审计校验)
           │
           └──→ 响应用户
```

### 2. 意图分类

| 一级意图 | 二级意图 | 说明 |
|----------|----------|------|
| 信息查询 | 客户查询、订单查询、物流查询... | 查询类操作 |
| 工单管理 | 创建工单、审批工单 | 工单类操作 |
| 异常上报 | 上报问题 | 异常处理 |

### 3. 工具调用

系统通过 MCP 协议调用外部工具：

- `query_customer`: 查询客户信息
- `query_order`: 查询订单信息
- `query_shipment`: 查询物流信息
- `create_work_order`: 创建工单
- `approve_work_order`: 审批工单

---

## Harness Engineering

系统已集成 Harness Engineering 工程化能力，提供三层增强：

### Layer 1: 配置化约束
- 业务规则配置化 (YAML)
- 参数预检装饰器

### Layer 2: 验证与可观测
- Prometheus Metrics (`/metrics`)
- 结构化日志 (JSON)
- 按需 Trace 收集
- Evals 评估框架

### Layer 3: 反馈与持续改进
- 错误聚类分析
- 周度报告生成

详见: `supply_chain_agent/harness/playbook.md`

---

## 快速开始

### 1. 启动服务

```bash
cd /root/Supply-Chain-Agent
python -m supply_chain_agent.app
```

### 2. 发送请求

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "查询客户123的订单信息"}'
```

### 3. 查看监控

```bash
# Prometheus Metrics
curl http://localhost:8000/metrics

# Trace 查询
python -m supply_chain_agent.harness.observability.trace_cli --status error
```

---

## 目录结构

```
supply_chain_agent/
├── agents/           # Agent 实现
│   ├── planner.py    # Planner Agent
│   ├── parser.py     # Parser Agent
│   ├── executor.py   # Executor Agent
│   └── auditor.py    # Auditor Agent
├── graph/            # LangGraph 工作流
│   └── workflow.py   # 状态图定义
├── tools/            # MCP 工具
├── memory/           # 记忆系统
├── harness/          # Harness Engineering
│   ├── rules/        # 业务规则
│   ├── observability/# 可观测性
│   ├── evals/        # Evals 评估
│   ├── feedback/     # 反馈改进
│   └── spec/         # 规范文件
├── prompts/          # Prompt 模板
├── config.py         # 配置管理
└── app.py            # FastAPI 应用
```

---

## 关键配置

### 环境变量

```bash
# LLM 配置
OPENAI_API_KEY=sk-xxx
OPENAI_MODEL=gpt-4

# 数据库配置
SUPPLY_CHAIN_DB_HOST=localhost
SUPPLY_CHAIN_DB_PORT=3306

# Harness 配置
HARNESS_RULES_ENABLED=true
HARNESS_METRICS_ENABLED=true
HARNESS_TRACE_ENABLED=true
```

---

## 相关文档

- [Harness Engineering 设计文档](./docs/Harness%20Engineering%20Design.md)
- [Harness Playbook](./supply_chain_agent/harness/playbook.md)
- [API 文档](http://localhost:8000/docs)

---

*文档版本: 1.0*
*最后更新: 2026-06-07*
