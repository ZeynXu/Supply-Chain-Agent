# Supply Chain Agent - 智能供应链工单处理Agent系统

## 产品概述

L3级自主Agent系统，为供应链运营团队提供协作副驾驶能力。基于LangGraph构建的多智能体协作系统，支持意图识别、工具调用、结果审计的完整工单处理流程。

**核心特性**：
- 🎯 四Agent星型拓扑架构（总控 + 解析 + 调度 + 审计）
- 🔄 LangGraph状态机工作流，支持Human-in-the-loop
- 🧠 三级记忆系统（短期 + 工作 + 长期）
- 🛡️ 熔断器保护与智能降级机制

## 技术栈

| 层级 | 技术 |
|------|------|
| **Agent框架** | LangGraph + LangChain |
| **LLM** | 智谱GLM-4.7（可配置其他） |
| **API服务** | FastAPI + Uvicorn |
| **前端** | React 18 + TypeScript + Ant Design 5 |
| **向量存储** | ChromaDB |
| **关系存储** | SQLite |

## 项目结构

```
Supply_Chain_Agent/
├── data/                          # 数据目录（向量库、检查点、SQLite）
├── docs/                          # 项目文档
├── supply_chain_agent/            # 主模块
│   ├── agents/                    # Agent定义
│   ├── tools/                     # MCP工具实现
│   ├── graph/                     # LangGraph工作流
│   ├── memory/                    # 记忆系统
│   ├── prompts/                   # Prompt模板
│   ├── monitoring/                # 监控系统
│   ├── tests/                     # 测试套件
│   ├── frontend/                  # React前端
│   ├── app.py                     # FastAPI应用入口
│   ├── config.py                  # 配置管理
│   └── requirements.txt           # Python依赖
└── supply_chain_agent.egg-info/   # 包信息
```

## 快速开始

### 环境要求

- Python 3.9+
- Node.js 18+（仅前端需要）

### 安装与启动

```bash
# 1. 安装后端依赖
pip install -r supply_chain_agent/requirements.txt

# 2. 启动后端服务（自动启动MCP服务器）
python -m supply_chain_agent --mode web --port 8000

# 3. 启动前端（另开终端）
cd supply_chain_agent/frontend && npm install && npm run dev
```

### 访问地址

| 服务 | 地址 |
|------|------|
| React前端 | http://localhost:3000 |
| FastAPI后端 | http://localhost:8000 |
| API文档 | http://localhost:8000/api/docs |

## 使用示例

### API调用

```bash
# 查询订单物流
curl -X POST http://localhost:8000/api/process \
  -H "Content-Type: application/json" \
  -d '{"query": "查一下PO-2026-001的货到哪了？"}'

# 创建工单
curl -X POST http://localhost:8000/api/workorders \
  -H "Content-Type: application/json" \
  -d '{"type": "quality_inspection", "type_name": "质量检验", "related_order": "PO-2026-001", "description": "到货质量抽检"}'
```

### Python SDK

```python
import asyncio
from supply_chain_agent.agents.orchestrator import OrchestratorAgent

async def main():
    agent = OrchestratorAgent()
    result = await agent.process("查一下PO-2026-001的物流状态")
    print(result["response"])

asyncio.run(main())
```

## 支持的意图

| 意图类型 | 示例输入 |
|----------|----------|
| 状态查询 | "查一下PO-2026-001的物流状态" |
| 工单创建 | "创建质量检验工单，订单PO-2026-001需要检验" |
| 异常上报 | "报告物流延迟问题，订单PO-2026-002预计延迟3天" |
| 审批流转 | "审批工单WO-2026-001，质量合格" |

## MCP工具

| 工具 | 功能 |
|------|------|
| `query_order_status` | 查询订单详情 |
| `get_logistics_trace` | 查询物流轨迹 |
| `create_work_order` | 创建工单 |
| `report_issue` | 上报异常 |
| `approve_work_order` | 提交审批（需用户确认） |

## 性能指标

| 指标 | 目标值 | 实际值 |
|------|--------|--------|
| 任务成功率 | > 65% | **72.0%** |
| 平均响应时间 | < 3秒 | **2.10秒** |
| 用户采纳率 | > 40% | **61.2%** |
| 工具可用率 | > 95% | **96.0%** |

## 更多文档

- [产品需求文档](../docs/PRD-V1.0.md)
- [API文档](../docs/API_DOCUMENTATION.md)
- [部署指南](../docs/DEPLOYMENT_GUIDE.md)
- [项目研究报告](../docs/PROJECT_RESEARCH_REPORT.md)

## 许可证

MIT License
