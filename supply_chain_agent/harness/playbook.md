# Harness Engineering 运维手册

本文档描述如何运维 Harness Engineering 系统。

---

## 1. 特性开关

通过环境变量控制 Harness 各特性的开关：

```bash
# Layer 1: 配置化约束
export HARNESS_RULES_ENABLED=true           # 启用业务规则审计
export HARNESS_RULES_PATH=/path/to/rules.yaml  # 自定义规则文件路径

# Layer 2: 可观测性
export HARNESS_STRUCTURED_LOGS=true         # 启用结构化日志
export HARNESS_METRICS_ENABLED=true         # 启用 Prometheus Metrics
export HARNESS_TRACE_ENABLED=true           # 启用 Trace 收集
export HARNESS_TRACE_SAMPLE_RATE=0.01       # Trace 采样率 (1%)
export HARNESS_TRACE_DIR=/root/autodl-tmp/harness-traces  # Trace 存储目录

# Layer 2: Evals
export HARNESS_EVALS_LEVEL=1                # Evals 等级 (0=禁用, 1=门禁, 2=告警)

# 可选功能
export HARNESS_PRE_CHECK=false              # 参数预检装饰器
```

---

## 2. 业务规则配置

### 2.1 规则文件位置

默认规则文件：`supply_chain_agent/harness/rules/business_rules.yaml`

### 2.2 规则格式

```yaml
version: "1.0"
rules:
  - id: "rule_id"              # 规则唯一标识
    name: "规则名称"            # 规则显示名称
    enabled: true              # 是否启用
    severity: "block"          # 严重级别: block, warn, notify
    condition: "amount > 100"  # 条件表达式
    action: "reject"           # 触发动作
    message: "错误消息"         # 提示消息
    metadata:                  # 元数据（可选）
      source: "业务规范"
      effective_date: "2026-01-01"
```

### 2.3 条件表达式

支持的表达式语法：

- 比较操作: `>`, `<`, `>=`, `<=`, `==`, `!=`
- 逻辑操作: `and`, `or`, `not`
- 包含操作: `in`, `not in`
- 字典访问: `order.get('status')`

允许的变量：
- `work_order`: 工单信息
- `order`: 订单信息
- `customer`: 客户信息
- `shipment`: 物流信息
- `action`: 操作类型
- `comment`: 审批意见
- `amount`, `status`, `type`: 常用字段

### 2.4 热加载

规则文件支持热加载（需要安装 watchdog）：

```python
from supply_chain_agent.harness.rules import RuleLoader

loader = RuleLoader(auto_reload=True)
```

---

## 3. Prometheus Metrics

### 3.1 访问 Metrics

```bash
curl http://localhost:8000/metrics
```

### 3.2 可用指标

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
| `agent_trace_samples_total` | Counter | Trace 采样数 |

---

## 4. Trace 收集

### 4.1 Trace 存储

Trace 文件存储在 `/root/autodl-tmp/harness-traces/` 目录，按天分区：

```
/root/autodl-tmp/harness-traces/
├── 2026-06-07.jsonl
├── 2026-06-08.jsonl
└── ...
```

### 4.2 Trace 格式

每行一个 JSON 对象：

```json
{
  "trace_id": "abc123",
  "span_id": "span001",
  "operation": "parse_input",
  "start_time": "2026-06-07T10:00:00Z",
  "end_time": "2026-06-07T10:00:01Z",
  "duration_ms": 1000,
  "status": "ok",
  "attributes": {},
  "events": []
}
```

### 4.3 查询 Trace

使用 trace_cli 工具：

```bash
# 查询所有错误 Trace
python -m supply_chain_agent.harness.observability.trace_cli --status error

# 查询指定 Trace ID
python -m supply_chain_agent.harness.observability.trace_cli --trace-id abc123

# 查询指定日期
python -m supply_chain_agent.harness.observability.trace_cli --date 2026-06-07

# 详细输出
python -m supply_chain_agent.harness.observability.trace_cli --status error --verbose
```

### 4.4 手动触发 Trace

```python
from supply_chain_agent.harness.observability import trace_context

with trace_context("my_operation", "trace-123") as span_id:
    # 执行操作
    pass
```

---

## 5. Evals 评估

### 5.1 运行 Evals

```bash
# 运行 Level 1 门禁评估
pytest -m eval --level=1

# 运行所有评估
pytest -m eval
```

### 5.2 评估等级

| 等级 | 名称 | 说明 |
|------|------|------|
| Level 1 | 门禁 | 必须通过才能部署 |
| Level 2 | 告警 | 失败只告警 |
| Level 3 | 手动 | 可选执行 |

---

## 6. 错误分析

### 6.1 生成错误报告

```bash
# 分析最近 7 天的错误
python -m supply_chain_agent.harness.feedback.cluster_errors --days 7

# 输出到文件
python -m supply_chain_agent.harness.feedback.cluster_errors --output report.json
```

### 6.2 生成周度报告

```bash
# 生成当前周的报告
python -m supply_chain_agent.harness.feedback.weekly_report

# 生成指定周的报告
python -m supply_chain_agent.harness.feedback.weekly_report --year 2026 --week 23
```

---

## 7. 常见问题排查

### 7.1 Metrics 端点无数据

检查：
1. `HARNESS_METRICS_ENABLED=true` 是否设置
2. FastAPI 应用是否正确初始化

### 7.2 Trace 未记录

检查：
1. `HARNESS_TRACE_ENABLED=true` 是否设置
2. Trace 目录是否有写入权限
3. 采样率是否过低（默认 1%）

### 7.3 规则未生效

检查：
1. 规则 `enabled` 字段是否为 `true`
2. 规则文件格式是否正确
3. 条件表达式语法是否正确

---

## 8. 性能影响

| 特性 | 性能影响 | 建议 |
|------|----------|------|
| 业务规则审计 | <1ms/规则 | 规则数 < 20 |
| 结构化日志 | 忽略不计 | 默认开启 |
| Prometheus Metrics | 忽略不计 | 默认开启 |
| Trace (1%采样) | 几乎无影响 | 生产环境建议 1% |
| Trace (错误) | ~50ms | 仅错误时记录 |

---

*文档版本: 1.0*
*最后更新: 2026-06-07*
