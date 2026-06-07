# 智能供应链工单处理Agent系统——Harness Engineering详细设计文档

**文档版本**：V1.0
**适用版本**：PROJECT_RESEARCH_REPORT.md
**设计范式**：Harness Engineering（驾驭工程）
**核心哲学**：Human Steer, Agents Execute（人类掌舵，智能体执行）
**核心原则**：**增强而非替换，配置化而非框架化，可选而非强制**

---

## 1. 设计定位与范围

### 1.1 本设计的核心命题

为现有Supply-Chain-Agent系统（四Agent星型拓扑 + LangGraph + MCP工具）**增加工程化能力**，包括：
- 业务规则的配置化审计
- 关键执行链路的可观测性（Metrics + Logs + Trace）
- 核心场景的轻量级验证（Evals）
- 错误驱动的持续改进流程

**非目标**：
- 不重构现有四Agent架构
- 不引入新的编排层
- 不强制要求全量改造

### 1.2 与现有系统的关系

| 现有组件 | Harness增强方式 |
|----------|----------------|
| **Auditor Agent** | 扩展审计规则为可配置YAML，支持动态加载 |
| **Executor Agent** | 增加装饰器级参数预检（可选） |
| **LangGraph工作流** | 不干预，仅通过hook记录Trace |
| **Memory系统** | 复用ChromaDB存储Evals结果 |
| **app.py Metrics** | 升级为Prometheus exporter |
| **日志系统** | 增加结构化JSON日志 |

---

## 2. Harness三层增强模型（替代七层）

为简化设计，将Harness能力收敛为三个可独立选用的层次：

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

所有特性均可通过环境变量开关，默认关闭，按需开启。

---

## 3. Layer 1：配置化约束层（详细设计）

### 3.1 扩展Auditor Agent：规则配置化

**现状**：Auditor硬编码了`AUDIT_RULES`列表（如missing_tracking_number等）。

**增强**：支持从YAML文件加载业务审计规则，热加载。

```yaml
# harness/business_rules.yaml
version: "1.0"
rules:
  - id: "high_value_approval"
    name: "大额审批需升级"
    severity: "block"
    condition: "work_order.amount > 500000 and work_order.type == '审批'"
    action: "require_approval_level: director"
    message: "订单金额超过50万，需要总监级审批"

  - id: "reject_cancelled_order"
    name: "已取消订单不可审批"
    severity: "block"
    condition: "order.status == 'cancelled'"
    action: "reject"
    message: "订单已取消，无法审批"

  - id: "customer_risk_check"
    name: "客户风险等级D级需上报"
    severity: "warn"
    condition: "customer.risk_level == 'D'"
    action: "escalate"
    message: "客户风险等级为D，建议上报风控"
```

**实现**：
- 在`AuditorAgent`中增加`load_business_rules()`方法。
- 在`audit_node`中，对工具结果评估规则条件（使用Python `eval`受限环境或自定义DSL）。
- 规则条件表达式使用`safe_eval`（只允许访问预定义变量：work_order, order, customer）。

### 3.2 参数预检装饰器（可选）

为`ExecutorAgent._execute_tool`增加装饰器，在调用前执行额外校验（如业务级参数依赖）。

```python
# 可选启用，默认关闭
def with_pre_check(checks: List[Callable]):
    def decorator(func):
        @wraps(func)
        async def wrapper(self, tool_name, params):
            if os.getenv("HARNESS_PRE_CHECK", "false").lower() == "true":
                for check in checks:
                    check(tool_name, params)
            return await func(self, tool_name, params)
        return wrapper
    return decorator
```

该装饰器不替换现有参数验证，仅增加额外检查（如order_id与work_order_id的关联性）。

### 3.3 AGENTS.md与SPEC规范文件

**保留初版设计**，但简化内容，聚焦于核心约束和角色说明。

目录结构：
```
supply_chain_agent/
├── AGENTS.md                     # 入口地图（~80行）
├── harness/
│   ├── business_rules.yaml       # 业务审计规则
│   ├── spec/
│   │   ├── intent_schema.json    # 意图输出Schema
│   │   └── tool_params_schema.json
│   └── guides/
│       └── error_handling.md     # 错误处理指南
```

---

## 4. Layer 2：验证与可观测层

### 4.1 增强Metrics（Prometheus）

**现状**：`app.py`中有简单的内存字典。

**增强**：暴露Prometheus端点，采集标准指标。

```python
# monitoring/metrics.py
from prometheus_client import Counter, Histogram, Gauge, generate_latest

REQUEST_COUNT = Counter('agent_requests_total', 'Total requests', ['intent', 'status'])
REQUEST_DURATION = Histogram('agent_request_duration_seconds', 'Request latency')
TOOL_CALL_COUNT = Counter('agent_tool_calls_total', 'Tool calls', ['tool_name', 'status'])
CIRCUIT_BREAKER_STATE = Gauge('agent_circuit_breaker_state', 'Circuit breaker state', ['tool_name'])

# 在FastAPI中添加 /metrics 端点
@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type="text/plain")
```

### 4.2 结构化日志

修改现有日志配置，输出JSON格式，便于采集到ELK/Loki。

```python
# utils/logging_config.py
import json_logging
json_logging.init_non_web(enable_json=True)

# 使用方式
logger.info("agent_step", extra={
    "step": "parse_input",
    "thread_id": thread_id,
    "duration_ms": 45
})
```

### 4.3 按需Trace（轻量级）

**定位**：非全量追踪，仅用于问题复现和深度调试。

- **采样率**：默认1%（通过`HARNESS_TRACE_SAMPLE_RATE=0.01`）。
- **错误强制记录**：任何导致任务失败的执行全量记录。
- **存储**：JSON Lines格式，按天分区，保存7天。
- **查询工具**：`trace_cli.py` 支持按thread_id、时间、错误类型过滤。

实现方式：
- 在`Workflow.process_with_events`中，若满足采样条件，则开启Trace Collector。
- Trace Collector将关键状态变更写入`logs/traces/YYYY-MM-DD.jsonl`。

### 4.4 核心场景Evals

**理念**：只对最高价值的场景进行自动化验证，不追求全覆盖。

**Evals类型**：
- **Level 1（门禁）**：核心意图识别、审批主流程、异常上报。必须通过才能部署。
- **Level 2（告警）**：边界情况、降级响应。失败只告警。
- **Level 3（手动）**：性能、压力测试。可选执行。

**实现**：
- 从现有`tests/`目录中抽取3-5个核心测试用例，包装为Evals。
- 使用现有pytest框架，增加`@pytest.mark.eval`标记。
- 运行命令：`pytest -m eval --level=1`

**不引入新的Mock框架**：复用现有测试Mock（`unittest.mock`或`pytest-mock`）。

---

## 5. Layer 3：反馈与持续改进层

### 5.1 错误聚类报告（半自动）

每周运行一次脚本，分析过去7天的日志和Trace：

- 按错误类型分组（如`MissingParameterError`、`ToolTimeoutError`）
- 统计频率、影响会话数
- 输出Markdown报告，发送至团队。

脚本实现：`harness/scripts/cluster_errors.py`，使用简单的正则+计数器。

### 5.2 周度分析流程（人工主导）

**流程**：
1. 周一运行脚本生成错误报告。
2. 团队评审（15分钟）：选出Top 3错误模式。
3. 针对每个模式，确定Harness改进项（规则补充、Evals补充、代码修复）。
4. 分配任务，下周迭代。

**输出**：`harness/improvements/YYYY-WW.md` 记录改进项。

### 5.3 Harness Playbook

编写运维手册，内容包括：
- 如何开启/关闭Harness特性（环境变量）
- 如何修改业务规则（YAML格式）
- 如何手动触发Trace记录
- 常见问题排查步骤

存放路径：`harness/playbook.md`

---

## 6. 实施计划（修正版）

### 总体周期：8周 + 持续迭代

| 阶段 | 时长 | 核心产出 | 验收标准 |
|------|------|----------|----------|
| **Phase 1：基础增强** | 4周 | 业务规则配置化、结构化日志、Prometheus Metrics、AGENTS.md | 1. Auditor可加载YAML规则并拦截违规操作<br>2. /metrics端点有5+指标<br>3. 日志为JSON格式 |
| **Phase 2：可观测性** | 3周 | 按需Trace、核心Evals（Level 1） | 1. Trace采样生效，错误全量记录<br>2. 3个核心Evals通过 |
| **Phase 3：反馈闭环** | 1周 | 错误聚类脚本、周度流程文档 | 脚本可生成报告，团队执行一次周度分析 |

**并行任务**：AGENTS.md和SPEC规范可在Phase 1内完成，共1周。

### 详细任务分解（人天估算）

| 任务 | 人天 | 说明 |
|------|------|------|
| Phase 1 业务规则YAML设计 | 2 | 定义规则格式，编写解析器 |
| 扩展AuditorAgent | 5 | 集成规则加载、评估、拦截逻辑 |
| 结构化日志改造 | 2 | 修改所有logger调用 |
| Prometheus Metrics集成 | 2 | 添加端点，埋点关键位置 |
| AGENTS.md编写 | 1 | 基于现有架构撰写 |
| Phase 2 Trace实现 | 5 | 采样、写入JSONL、查询工具 |
| Evals（3个核心） | 3 | 从现有测试抽取或新增 |
| Phase 3 聚类脚本 | 2 | 日志分析，生成报告 |
| 文档与Playbook | 2 | 运维手册 |
| 缓冲时间 | 6 | 应对意外问题 |
| **总计** | **30人天** | 约6人周（1人全职） |

---

## 7. 性能与成本影响（量化）

| 特性 | 性能影响 | 成本影响 | 默认状态 |
|------|----------|----------|----------|
| 业务规则审计 | 每个规则评估<1ms（纯Python），总规则<20条 | 无 | **开启**（替代硬编码） |
| 结构化日志 | 忽略不计（异步写入） | 存储增加~20% | **开启** |
| Prometheus Metrics | 忽略不计 | 无 | **开启** |
| 按需Trace | 采样1%时几乎无影响；错误全量记录时增加~50ms | 存储：每日~50MB（采样+错误） | 采样1%，错误全量 |
| Evals（CI） | 执行时间+2分钟 | 无 | 仅部署前触发 |

**降级开关**：
```bash
HARNESS_TRACE_ENABLED=false
HARNESS_PRE_CHECK=false
HARNESS_EVALS_LEVEL=0   # 0=禁用
```

---

## 8. 与现有代码的集成点（零侵入原则）

| 集成点 | 方式 | 是否修改现有代码 |
|--------|------|------------------|
| Auditor扩展 | 新增`_load_business_rules`，在`audit`方法中调用 | **修改**（但为扩展，不影响原有逻辑） |
| 结构化日志 | 替换`logging.basicConfig`为json_logging | **修改**初始化代码 |
| Metrics | 在`app.py`新增`/metrics`路由，埋点使用装饰器或中间件 | **修改**（少量） |
| Trace | 在`workflow.py`的`process_with_events`中添加条件分支 | **修改**（加if） |

**总体评估**：修改现有代码约10处，总行数<200行，风险可控。

---

## 9. 设计文档优点保留与改进对照

| 初版优点 | 保留/改进方式 |
|----------|---------------|
| AGENTS.md理念 | 保留，简化内容 |
| 缺口分析准确 | 保留分析结论 |
| 文档结构清晰 | 保留结构，调整内容 |
| 配置设计合理 | 保留YAML配置方式 |

---

## 10. 风险与应对（修正）

| 风险 | 概率 | 影响 | 应对措施 |
|------|------|------|----------|
| 规则评估性能意外高 | 低 | 中 | 规则条件限制为O(1)操作，禁止数据库查询 |
| Trace存储膨胀 | 中 | 低 | 采样+自动轮转，保留7天，可用cron清理 |
| 团队不熟悉新流程 | 中 | 中 | 提供Playbook，前两次周度分析由设计者主持 |
| Evals维护懈怠 | 中 | 中 | 仅维护3个核心Evals，与pytest集成，不增加额外负担 |

---

## 11. 附录：配置与代码示例

### 11.1 业务规则YAML示例（完整）

```yaml
# harness/business_rules.yaml
rules:
  - id: "high_value_approval"
    enabled: true
    severity: block
    condition: |
      work_order.get('amount', 0) > 500000 and 
      work_order.get('type') == '审批'
    action: "require_approval_level: director"
    message: "订单金额超过50万，需要总监级审批"

  - id: "reject_cancelled_order"
    enabled: true
    severity: block
    condition: "order.get('status') == 'cancelled'"
    action: "reject"
    message: "订单已取消，无法审批"
```

### 11.2 环境变量清单

```bash
# Harness特性开关
HARNESS_RULES_ENABLED=true          # 业务规则审计
HARNESS_STRUCTURED_LOGS=true        # JSON日志
HARNESS_METRICS_ENABLED=true        # Prometheus
HARNESS_TRACE_ENABLED=true          # 按需Trace
HARNESS_TRACE_SAMPLE_RATE=0.01      # 1%采样
HARNESS_PRE_CHECK=false             # 参数预检装饰器
HARNESS_EVALS_LEVEL=1               # 1=门禁, 2=告警, 0=禁用
```

### 11.3 周度错误分析报告模板

```markdown
# 错误分析周报 - 2026-06-14

## Top 3 错误类型
1. MissingParameterError (order_id) - 12次
   - 影响会话: [thread-123, thread-456]
   - 根因: 订单号格式变化（新增前缀"PO-"）
   - 建议: 更新参数提取规则正则

2. ToolTimeoutError (query_customer_statistics) - 5次
   - 影响会话: ...
   - 根因: 数据库慢查询
   - 建议: 增加查询超时时间或优化索引

## 已分配的改进项
- [ ] 更新 `executor.py` 参数提取逻辑（负责人：张三）
- [ ] 调整 `supply_chain_db.py` 索引（负责人：李四）
```

---

## 12. 总结

本Harness Engineering设计遵循以下原则：
1. **尊重现状**：不推翻现有四Agent架构和LangGraph工作流。
2. **务实可落地**：每个特性都给出明确的人天估算和性能影响。
3. **可选不强制**：通过环境变量控制，默认关闭核心功能。
4. **渐进增强**：分三期实施，每期独立交付价值。

最终目标不是构建一个“完美的Harness框架”，而是**以最小成本为现有系统增加工程化护栏**，提升可观测性和可维护性，并建立轻量级的持续改进流程。

---
