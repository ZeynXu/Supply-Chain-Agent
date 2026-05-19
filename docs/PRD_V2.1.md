### **智能供应链工单处理Agent系统 - 生产级基础设施补充设计**

---

### 1. 设计背景与目标

#### 1.1 为什么要补充基础设施设计？

原详细设计方案聚焦于 Agent 的智能协作逻辑、功能模块和工具调用，已具备完整的业务闭环能力。但若该系统作为企业级平台正式上线运营，将面临以下非功能性挑战：

- **多租户并发**：多个供应链运营专员同时处理不同工单，Agent 实例需要弹性伸缩。
- **长时任务处理**：部分工单涉及多步骤审批或跨系统查询，耗时较长，需要异步解耦。
- **LLM服务可靠性**：云端LLM API可能因网络波动或配额限制导致调用失败，需要重试与熔断保护。
- **系统可观测性**：Agent 行为链路长，需追踪一次工单处理到底经过了哪些节点、调用了哪些工具、耗时如何。
- **依赖服务故障隔离**：MCP Server、向量数据库等依赖需要健康检查与自动恢复。

**目标**：在不改变 Agent 业务逻辑的前提下，通过引入容器化、编排与中间件技术，将系统升级为具备**弹性伸缩、故障自愈、灰度发布、端到端可观测**能力的生产级平台，并使其无缝融入企业现有 IT 基础设施。

#### 1.2 核心设计原则

- **无侵入性**：Agent 核心代码不变，通过外挂基础设施层增强。
- **渐进式落地**：支持从单机 Docker Compose 快速启动到完整 K8s 集群的平滑演进。
- **技术栈企业兼容性**：优先选择业界标准、云原生生态成熟且国内招聘市场认可的技术组件。

---

### 2. 容器化设计

#### 2.1 服务拆解与镜像规划

我们将原单进程应用拆分为一组松耦合的微服务，每个服务打包为独立的 Docker 镜像，形成清晰的服务边界和独立的发布节奏。

| 服务名称 | 职责 | 关键依赖 | 镜像基础 |
|:---|:---|:---|:---|
| **Agent Orchestrator** | 总控Agent、解析师、调度员、审计员的图执行引擎，提供 API 接口 | LangGraph, MCP Client | `python:3.11-slim` + 自定义层 |
| **MCP Tool Server** | 封装 Mock 企业内部 API，暴露标准 MCP 协议 | FastMCP | `python:3.11-slim` |
| **Milvus** | 向量存储与检索 | 无 | 官方 `milvusdb/milvus` 镜像 |
| **Evaluation Service** | Ragas 评测定时任务 | Agent Orchestrator API | `python:3.11-slim` |

**镜像优化策略**：采用多阶段构建，将 Python 包等重依赖固化在基础镜像层，业务代码层保持不变，实现构建加速和体积控制。

#### 2.2 本地开发与一键启动

为降低协作门槛，我们使用 **Docker Compose** 定义本地开发和演示环境，一条命令即可拉起全部服务栈：

```yaml
# docker-compose.dev.yml 片段示意
services:
  orchestrator:
    build: ./agents
    depends_on:
      - mcp-server
      - milvus
    environment:
      - MCP_SERVER_URL=http://mcp-server:8080
      - MILVUS_HOST=milvus
  mcp-server:
    build: ./tools
  milvus:
    image: milvusdb/milvus:latest
    ports:
      - "19530:19530"
```

**产品价值**：任何开发者在自己的机器上执行 `docker compose up -d`，即可获得与生产环境一致的全栈 Agent 系统，极大降低环境差异导致的问题排查成本。

---

### 3. 容器编排设计

当系统需要面向多用户、处理多并发的工单时，我们引入 Kubernetes 进行声明式编排。

#### 3.1 Kubernetes 集群部署架构

```
                         ┌──────────────┐
                         │   Ingress    │ (域名路由/TLS)
                         └──────┬───────┘
                                │
                         ┌──────▼───────┐
                         │  API Gateway │ (Envoy/NGINX)
                         └──────┬───────┘
                    ┌───────────┼────────────┐
           ┌────────▼────┐ ┌───▼─────┐ ┌────▼────────┐
           │ Orchestrator│ │  MCP    │ │ Evaluation   │
           │  Deployment │ │ Server  │ │ CronJob      │
           └─────┬───────┘ └─────────┘ └──────────────┘
                 │
                 ▼
           ┌───────────┐
           │  Milvus   │
           │StatefulSet│
           └───────────┘
```

- **Agent Orchestrator**：无状态部署（`Deployment`），通过 HPA（水平自动伸缩）根据 CPU/内存或自定义指标（如请求队列长度）动态扩展副本。
- **Milvus**：有状态服务，使用 `StatefulSet` 确保稳定的网络标识和持久存储卷（PVC）。
- **Evaluation Service**：作为批处理任务，以 `CronJob` 形式每日自动运行评测，生成报告发送给管理员。

#### 3.2 服务发现与配置管理

- **服务发现**：Kubernetes 原生的 Service 和 DNS（如 `http://orchestrator.default.svc.cluster.local:8000`）使得 Agent Orchestrator 能无感知地发现 MCP Server、Milvus 等依赖。
- **配置管理**：使用 `ConfigMap` 存储非敏感的 Agent 配置（如意图分类阈值、重试次数），使用 `Secret` 管理 MCP Server 的 Mock 鉴权 Token 等敏感信息，与镜像解耦，支持配置热更新。

#### 3.3 弹性与滚动更新

- **HPA 规则**：当 Agent Orchestrator 的请求并发数超过 10 时，自动扩展副本至 3，最大 10 个副本。
- **滚动更新策略**：设置 `maxSurge: 1, maxUnavailable: 0`，确保在发布新版本时服务永不中断。结合 Readiness Probe 检查 Agent 的 `/health` 端点，确保新 Pod 就绪后旧 Pod 才终止。

**产品价值**：编排层让系统面对突发工单高峰时不会瘫痪，并且发版对用户透明，这些都是企业级 SaaS 的标准承诺。

---

### 4. 中间件选型与应用

中间件是提升系统韧性、异步处理能力和可观测性的关键。

| 中间件 | 选型 | 核心应用场景 |
|:---|:---|:---|
| **消息队列** | **Redis** (小规模) / **Apache Kafka** (企业级) | 解耦 Agent 的长时间工具调用，实现异步工单处理 |
| **缓存** | **Redis** | 缓存高频工单模板、用户权限、工具调用降级数据 |
| **可观测性** | **OpenTelemetry + Jaeger + Prometheus + Grafana** | 全链路追踪、指标收集、日志聚合与告警 |
| **配置中心** | **Kubernetes ConfigMap/Secret** (附带) | 统一管理 Agent 行为参数，实时生效 |

#### 4.1 消息队列实现异步工单处理

当前架构为同步请求-响应模式，若某个工单需要执行耗时 30 秒的审批流，用户将长时间等待。引入消息队列后：

1. 用户发起工单请求。
2. Agent Orchestrator 将工单任务（含意图、槽位）序列化为消息，发布至 `workorder:new` 主题。
3. 后台 Worker（同样是 Agent Orchestrator 的副本，但角色分离）订阅消息，执行完整的图处理流程。
4. 完成后，将结果发布至 `workorder:result:{user_id}` 通道，前端通过 WebSocket 或轮询获取结果。

**队列选型策略**：
- **Redis Stream**：轻量，部署简单，适合 Demo 和初期版本，一条命令即可搭建。
- **Kafka**：持久化、高吞吐，适合真正企业上线，能保证工单不丢失，并支持回溯审计。

#### 4.2 Redis 缓存加速

- **工单处理模板缓存**：对于高频工单类型（如"物流查询"），将标准化的 Slot 填充模板和常用工具调用链序列化存入 Redis，Agent 可直接加载加速规划。
- **降级数据缓存**：当 MCP Tool Server 短暂不可用时，Agent 可读取 Redis 中缓存的最新一次成功查询结果（标记"缓存数据，可能过期"），避免直接报错。
- **会话状态外置存储**：若需要多副本无状态 Agent，可将当前会话的工作记忆（LangGraph State）备份至 Redis，实现会话在不同 Pod 间迁移。

#### 4.3 全链路可观测性体系

这是产品经理面试中极具亮点的部分。我们设计三层可观测性：

1. **链路追踪 (Tracing)**：在每个 Agent 决策节点和 MCP 工具调用处插入 OpenTelemetry Span，生成一次工单处理的完整调用瀑布图。在 Jaeger UI 中可查询"订单 PO-2026-001"的每一步耗时。
2. **指标监控 (Metrics)**：暴露 Prometheus 指标，如 `workorder_processed_total`（按意图分类）、`tool_call_duration_seconds`、`agent_loop_count`。在 Grafana 中构建看板，展示工单处理成功率、P99 延迟等核心 SLA 指标。
3. **日志聚合 (Logging)**：结构化日志（JSON 格式）输出到标准输出，通过 Fluentd 收集到 Elasticsearch，使用 Kibana 快速搜索错误日志。对于 Agent 特有的"推理链"，可以记录自定义事件，如"审计员发现数据异常"。

**产品价值**：当系统出现"为什么我的工单处理慢了？"的疑问时，可观测性体系能在 30 秒内定位是 LLM 调用慢、MCP 调用超时，还是代码逻辑死循环。这是从 Demo 到生产环境的最后一公里。

---

### 5. 端到端部署流程 (CI/CD 衔接)

为了实现敏捷迭代，我们为这套容器化系统设计一条简单的 GitOps 流水线：

1. 开发者提交代码到 Git 仓库的 `feature` 分支。
2. 触发 GitHub Actions 进行单元测试和镜像构建，推送带版本标签的镜像至私有仓库（如 Harbor）。
3. 合并到 `main` 分支后，自动更新部署仓库中的 Helm Chart 或 Kustomize 配置。
4. ArgoCD 监听部署仓库变化，自动同步至 Kubernetes 集群，完成灰度发布（先更新 10% 副本，观察指标后全量）。

这样，Agent 系统获得了与互联网公司同等级别的持续交付能力。
