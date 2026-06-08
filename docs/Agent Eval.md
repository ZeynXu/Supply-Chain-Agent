# 智能供应链工单处理Agent系统——Agent评估系统详细设计文档


**编制日期**：2026年6月7日

**核心设计理念**：**轨迹驱动评估 + 混合评价策略 + 持续改进闭环**

**核心原则**：全面覆盖Agent能力维度，可量化、可复现、可演进


## 一、项目现状与设计定位

### 1.1 已实现的Harness Engineering基础设施

经代码审查确认，Harness Engineering已于本项目实现，其核心组件如下：

| Harness组件 | 文件位置 | 功能描述 | 评估系统的使用方式 |
|-------------|----------|----------|-------------------|
| **Rules系统** | `harness/constraints/rule-config.yaml` | 业务规则配置化审计 | 消费规则库，验证Agent操作是否符合业务约束 |
| **AGENTS.md/SPEC** | `AGENTS.md` + `harness/spec/` | Agent行为指南与规范 | 作为评估基线，验证Agent行为是否符合规范 |
| **Evals系统** | `harness/evals/` | 场景验证集与运行器 | 复用Evals作为评估数据源和回归测试框架 |
| **Trace采集** | `harness/observability/trace.py` | 结构化Trace记录与存储 | 消费Trace数据，驱动轨迹评估 |
| **Metrics收集** | `harness/observability/metrics.py` | Prometheus指标导出 | 复用指标作为生产监控数据源 |
| **错误聚类** | `harness/feedback/cluster_errors.py` | 失败模式聚类分析 | 复用聚类结果，作为评估报告的数据来源 |
| **周度报告** | `harness/feedback/weekly_report.py` | 周度改进报告生成 | 评估报告与之协同输出统一看板 |

### 1.2 评估系统的定位

本评估系统**不是**Harness Engineering的替代品或平行体系，而是**扩展与增强层**：

- **扩展**：在Harness现有能力基础上，增加**轨迹评分**、**LLM Judge**、**黄金集校准**等高级评估能力
- **增强**：为Harness的Evals、Trace、Metrics等基础能力提供**多维度评价聚合**与**自动化分析**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    已实现的 Harness Engineering                               │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐           │
│  │   Rules     │ │   Evals     │ │   Trace     │ │  Metrics    │           │
│  │   规则引擎   │ │  验证集     │ │  轨迹采集   │ │  指标收集   │           │
│  └──────┬──────┘ └──────┬──────┘ └──────┬──────┘ └──────┬──────┘           │
│         │                │                │                │                │
│         └────────────────┼────────────────┼────────────────┘                │
│                          │                │                                 │
│                          ▼                ▼                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                        评估系统（本设计）                                 ││
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   ││
│  │  │ 单元能力层  │→ │ 场景验证层  │→ │ 回归测试层  │→ │ 生产监控层  │   ││
│  │  │（Layer 1）  │  │（Layer 2）  │  │（Layer 3）  │  │（Layer 4）  │   ││
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘   ││
│  │        ↑                ↑                ↑                ↑            ││
│  │        └────────────────┴────────────────┴────────────────┘            ││
│  │                         │                                               ││
│  │                 ┌───────┴───────┐                                       ││
│  │                 │ 新增能力：    │                                       ││
│  │                 │ • 轨迹评分器  │                                       ││
│  │                 │ • LLM Judge   │                                       ││
│  │                 │ • 黄金集校准  │                                       ││
│  │                 │ • 评估报告    │                                       ││
│  │                 └───────────────┘                                       ││
│  └─────────────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.3 核心评估维度

基于Harness三层架构中的“可验证、可评估”目标，建立四维评估指标体系：

| 维度 | 核心指标 | 数据来源（Harness组件） |
|------|----------|------------------------|
| **功能正确性** | 任务完成率、工具调用正确率、意图识别准确率 | Evals运行器 + Trace采集 |
| **执行效率** | 平均响应时间、Token消耗、澄清循环成功率 | Metrics收集 + Trace采集 |
| **稳定性与鲁棒性** | 异常输入处理成功率、降级响应触发率 | 错误聚类 + Evals |
| **用户体验** | 帮助性评分、答案忠实度、用户采纳率 | LLM Judge + 黄金集 |


## 二、评估体系分层设计

### 2.1 Layer 1：单元能力层

**目标**：评估Agent各组件的独立能力，确保底层模块质量可靠。

#### 2.1.1 意图识别评估

基于Harness的Evals验证集运行器，评估ParserAgent的意图分类准确性。从生产Trace中抽取测试用例，构建覆盖7种一级意图和12种二级意图的测试集。

- **评估方式**：将`harness/evals/validation_set.yaml`中的测试用例扩展至65个有效意图组合，每个组合至少包含正向和边界两个测试用例
- **评估指标**：准确率、混淆矩阵、置信度得分分布（目标≥85%）

#### 2.1.2 工具调用正确性评估

消费Harness Trace采集的执行轨迹，验证工具调用的**决策边界**和**参数合法性**——正确判断是否该调用工具以及生成的参数是否符合Schema要求。

Harness已实现的参数验证逻辑（`executor.py`中的`_validate_tool_params`）作为确定性评估的第一道防线，本层在此基础上增加语义层面的决策正确性判断：

```python
def evaluate_tool_call(gold: ToolCallGold, actual: ToolCallActual) -> ToolCallEvalResult:
    """
    评估维度（权重配置匹配供应链场景优先级）：
    - 决策正确性（30%）：闲聊时不应触发工具调用
    - 工具选择（25%）：选择的工具是否匹配意图
    - 参数完整性（25%）：必填参数是否完整
    - 参数有效性（20%）：参数是否符合业务约束
    """
```

#### 2.1.3 审计规则评估

验证AuditorAgent对Harness业务规则库（`harness/constraints/rule-config.yaml`）的遵循程度。每个业务规则至少构造“合规”和“违规”两种场景进行测试，输出规则触发准确率、误报率和拦截及时性。

### 2.2 Layer 2：场景验证层

**目标**：验证Agent在各类业务场景下的端到端表现。

#### 2.2.1 场景覆盖矩阵

复用Harness Evals框架，构建基于意图组合的场景验证集。每个有效意图组合覆盖标准路径、缺失信息路径、边缘意图、错误恢复路径四种用例类型，总计约260个测试用例（65组合×4类）。

#### 2.2.2 九维轨迹评分

消费Harness Trace采集的执行轨迹，实现行业领先的九维轨迹评分模型，全面评估Agent的中间决策过程：

| 维度 | 权重（审批场景） | 评估内容 | 数据来源 |
|------|-----------------|----------|----------|
| 工具选择正确性 | 15% | 工具选型是否匹配意图 | Trace工具节点 |
| 参数完整性 | 10% | 参数是否满足Schema | Trace参数记录 |
| 参数有效性 | 10% | 参数是否业务合法 | Trace+规则引擎 |
| 执行顺序合理性 | 10% | 调用顺序是否符合逻辑 | Trace时间序 |
| 审计规则遵循 | 15% | 操作是否符合业务规则 | Harness Rules |
| 最终答案可达性 | 15% | 是否成功完成任务 | Trace最终输出 |
| 错误恢复能力 | 10% | 失败后的重试/降级策略 | Trace错误节点 |
| 澄清循环效率 | 5% | 3轮内完成信息收集 | Trace状态变化 |
| 响应时间合规性 | 10% | 执行时长不超阈值 | Trace耗时统计 |

**错误恢复能力评估**：基于Trace中的重试记录和降级触发记录，评估Agent在工具调用失败或异常时的恢复行为是否符合预期。

#### 2.2.3 边界与异常场景测试

基于Harness错误聚类结果（`harness/feedback/cluster_errors.py`），提取高频失败模式并构造专项测试用例：参数缺失处理、不存在的实体ID处理、跨会话混淆、超长输入处理、依赖服务不可用时的降级响应。

### 2.3 Layer 3：回归测试层

**目标**：在Harness配置或Agent代码变更后，自动运行回归测试，确保原有关键功能不退化。采用LangSmith Engine的生产数据驱动模式。

- **门禁机制**：部署前自动运行Level 1核心场景（P0用例约15个），通过率<90%时自动阻断发布
- **测试集来源**：从Harness Trace的生产失败样本中自动抽取，转化为回归测试用例
- **版本管理**：每次Harness升级后自动更新回归测试集

### 2.4 Layer 4：生产持续监控层

**目标**：基于Harness Metrics和Trace，实时监控生产环境中的Agent健康状态。

#### 2.4.1 监控指标与告警

| 监控项 | 数据来源 | 告警阈值 | 数据来源 |
|--------|----------|----------|----------|
| 任务成功率 | Harness Metrics | <75% | `harness/observability/metrics.py` |
| 工具调用异常率 | Harness Metrics | 实时偏离3σ基线 | `harness/observability/metrics.py` |
| 响应时间P99 | Harness Metrics | >5秒 | `harness/observability/metrics.py` |
| 澄清循环频繁触发 | Harness Trace | 单会话超过3次 | `harness/observability/trace.py` |
| 用户采纳率下降 | Harness Metrics | <40% | `harness/observability/metrics.py` |

#### 2.4.2 实时监控仪表盘

- **概览看板**：今日任务总数、成功率分布（按意图）、平均响应时间趋势
- **Drill-down模块**：按意图类型、按错误类型下钻分析
- **时间序列模块**：各指标时序曲线，支持与历史基线对比
- **Top失败模式模块**：基于Harness错误聚类的排名与根因摘要


## 三、核心组件详细设计

### 3.1 新增组件清单

| 组件 | 所属模块 | 功能 | 与Harness的关系 |
|------|----------|------|----------------|
| **TrajectoryScorer** | `evaluation/core/trajectory_scorer.py` | 九维轨迹评分器 | 消费`harness/observability/trace.py`的Trace数据 |
| **ToolCallValidator** | `evaluation/core/tool_call_validator.py` | 工具调用正确性评估器 | 复用`harness/evals/runner.py`的评估框架 |
| **LLMJudge** | `evaluation/judges/llm_judge.py` | LLM-as-Judge评分器 | 独立新增，用于主观维度评分 |
| **Calibrator** | `evaluation/judges/calibrator.py` | LLM Judge校准器 | 依赖黄金集，与Harness Evals协同 |
| **EvaluationReporter** | `evaluation/reports/generator.py` | 评估报告生成器 | 与`harness/feedback/weekly_report.py`协同输出 |

### 3.2 轨迹评分器

**设计目的**：将Harness Trace采集的非结构化轨迹数据转化为可量化的评分。

```python
# evaluation/core/trajectory_scorer.py

class TrajectoryScorer:
    """
    九维轨迹评分器
    输入：Harness Trace数据（trace_id, thread_id, steps, tool_calls, errors, audit_results）
    输出：9个维度的归一化评分 + 综合得分
    """
    
    def __init__(self, trace_fetcher, rule_engine):
        self.trace_fetcher = trace_fetcher  # 调用harness/observability/trace.py
        self.rule_engine = rule_engine      # 调用harness/constraints/rule_config.yaml
    
    async def score(self, thread_id: str, gold: Optional[GoldResult] = None) -> Score:
        trace = await self.trace_fetcher.get_trace(thread_id)
        
        scores = {
            'tool_selection': self._score_tool_selection(trace),
            'params_complete': self._score_params_completeness(trace),
            'params_valid': self._score_params_validity(trace),
            'execution_order': self._score_execution_order(trace),
            'audit_compliance': self._score_audit_compliance(trace, self.rule_engine),
            'answer_reachability': self._score_answer_reachability(trace, gold),
            'error_recovery': self._score_error_recovery(trace),
            'clarification_efficiency': self._score_clarification_efficiency(trace),
            'latency': self._score_latency(trace)
        }
        
        return Score(overall=self._weighted_average(scores), dimension_scores=scores)
```

### 3.3 LLM Judge

**设计目的**：对Agent输出的主观质量维度（帮助性、清晰度、忠实度）进行自动化评分。

#### 3.3.1 Judge模型选择

LLM作为评判者存在自偏好偏差——会系统性地偏向与其自身风格更相似的模型，在实际性能评估中约产生5-10%的影响。本设计选择**Claude 3.5 Sonnet**（独立厂商）作为Judge模型，以规避自偏好偏差。

**备选方案**：
- 若无法接入外部Judge API，使用GLM-4.7 Fast模式作为内部迭代的参考评分（产出结果标注“低置信度”）

#### 3.3.2 黄金集规模与校准流程

基于Cohen's Kappa阈值与样本量的数学关系，黄金集规模设计如下：

**黄金集目标规模**：200个配对样本。若Judge的Kappa约0.6，200个样本可在95%置信度下获得约±0.10的置信区间宽度。

**样本分配**：

| 评分维度 | 样本数 | 说明 |
|----------|--------|------|
| 格式正确性/参数完整性 | 60 | 客观维度，容易标注 |
| 帮助性/清晰度 | 80 | 半客观维度，需多轮校准 |
| 忠实度/无幻觉 | 60 | 供应链核心，需领域专家标注 |

**校准流程**：
1. 在黄金集上运行Judge，计算Cohen's Kappa
2. 若Kappa低于0.6，启动Rubric优化或Prompt调优
3. 每两周重新校准一次（与Harness周度反馈会议协同）
4. 保留校准结果的历史趋势

### 3.4 目录结构

```
supply_chain_agent/
├── harness/                              # 已实现的Harness Engineering
│   ├── constraints/rule-config.yaml      # 业务规则库（评估消费）
│   ├── evals/                            # Evals运行器（评估复用）
│   ├── observability/
│   │   ├── trace.py                      # Trace采集（评估消费）
│   │   └── metrics.py                    # Metrics收集（评估消费）
│   └── feedback/
│       ├── cluster_errors.py             # 错误聚类（评估复用）
│       └── weekly_report.py              # 周度报告（评估协同）
│
└── evaluation/                           # 评估系统（新增）
    ├── core/
    │   ├── trajectory_scorer.py          # 轨迹评分器
    │   └── tool_call_validator.py        # 工具调用评估器
    ├── judges/
    │   ├── llm_judge.py                  # LLM Judge评分器
    │   └── calibrator.py                 # 黄金集校准器
    ├── datasets/                         # 评估数据集（扩展自harness/evals/）
    │   ├── golden/                       # 200条人工标注黄金集
    │   └── regression/                   # 从生产失败抽取的回归测试集
    ├── runners/                          # 评估运行器（调用harness/evals/runner.py）
    │   └── eval_runner.py
    ├── monitoring/                       # 生产监控（消费harness/metrics + trace）
    │   └── dashboard.py
    └── reports/                          # 评估报告（与harness/weekly_report.py协同）
        └── generator.py
```


## 四、实施路线图

### 4.1 三阶段计划

| 阶段 | 时长 | 核心产出 | 与Harness协同 |
|------|------|----------|---------------|
| **Phase 1：轨迹评分基础** | 3周 | 轨迹评分器、工具调用评估器 | 消费Harness Trace数据，复用Evals框架 |
| **Phase 2：LLM Judge集成** | 4周 | LLM Judge、黄金集校准 | 与Harness周度报告协同，评估结果纳入周度会议 |
| **Phase 3：生产监控闭环** | 3周 | 生产监控仪表盘、自动化评估流程 | 消费Harness Metrics，与错误聚类形成闭环 |

### 4.2 关键里程碑

| 里程碑 | 时间节点 | 交付物 | 验收标准 | 依赖Harness组件 |
|--------|----------|--------|----------|----------------|
| M1：轨迹评分上线 | Phase 1 W3 | 九维轨迹评分器 | 可对Harness Trace进行多维度评分 | `harness/observability/trace.py` |
| M2：LLM Judge校准 | Phase 2 W2 | 校准报告、200条黄金集 | Kappa≥0.6 | `harness/evals/runner.py` |
| M3：评估报告协同 | Phase 2 W4 | 统一评估看板 | 与Harness周度报告共同发布 | `harness/feedback/weekly_report.py` |
| M4：生产监控上线 | Phase 3 W3 | 实时仪表盘 | 使用Harness Metrics数据展示健康状态 | `harness/observability/metrics.py` |


## 五、与Harness的集成接口

### 5.1 数据流

```
Harness Trace ──→ TrajectoryScorer ──→ 维度评分 ──┐
Harness Metrics ─→ 在线检测模块 ──→ 实时指标 ──┼──→ 统一评估看板
Harness Evals ───→ 场景验证器 ──→ 回归测试结果 ──┤
Harness Rules ───→ 规则遵循检查器 → 合规评分 ───┘
                                            │
                                            ▼
                              Harness Weekly Report（协同发布）
```

### 5.2 API集成示例

```python
# evaluation/runners/eval_runner.py

from harness.evals.runner import EvalRunner        # 复用Harness Evals
from harness.observability.trace import get_trace  # 复用Harness Trace
from harness.constraints.rule_engine import RuleEngine  # 复用Harness规则

class EvaluationOrchestrator:
    """评估编排器——整合Harness各组件能力"""
    
    def __init__(self):
        self.trace_fetcher = get_trace
        self.rule_engine = RuleEngine()
        self.eval_runner = EvalRunner()
        self.trajectory_scorer = TrajectoryScorer(self.trace_fetcher, self.rule_engine)
        self.llm_judge = LLMJudge()
    
    async def evaluate_thread(self, thread_id: str) -> FullEvaluation:
        """评估单个会话"""
        # 1. 获取Harness Trace数据
        trace = await self.trace_fetcher(thread_id)
        
        # 2. 运行Harness Evals验证
        eval_result = await self.eval_runner.run_on_thread(thread_id)
        
        # 3. 计算轨迹评分
        trajectory_score = await self.trajectory_scorer.score(thread_id)
        
        # 4. 主观质量评分
        quality_score = await self.llm_judge.score(trace.final_output)
        
        return FullEvaluation(
            eval_result=eval_result,
            trajectory_score=trajectory_score,
            quality_score=quality_score
        )
```


## 六、风险与应对

| 风险 | 概率 | 影响 | 应对措施 |
|------|------|------|----------|
| Harness组件变更导致集成断裂 | 中 | 中 | 定义明确的接口契约；版本兼容性测试纳入CI |
| LLM Judge评分偏差 | 高 | 中 | 黄金集校准Kappa≥0.6；低置信度评分标注告警 |
| 评估运行耗时长 | 中 | 低 | 回归测试分级执行；CI中仅运行核心测试集 |
| 与Harness周度报告数据不一致 | 中 | 低 | 评估报告与周度报告共用数据源；定期对账 |

**降级策略**：
- 若LLM Judge服务不可用，所有主观维度评分标注为“N/A（降级模式）”，仅报告客观维度和轨迹评分
- 若Harness Trace服务中断，暂停轨迹评分，仅依赖Evals进行功能验证


## 七、总结

本评估系统设计严格遵循以下原则：

1. **复用优先**：所有评估能力建立在已实现的Harness Engineering基础设施之上，不重复建设
2. **分层评估**：从单元能力到生产监控，四层递进，确保评估全覆盖
3. **轨迹驱动**：基于Harness Trace数据实现九维轨迹评分，评估Agent的完整决策链条
4. **持续演进**：从生产失败中学习，持续扩充评估集，形成闭环优化

**本评估系统与已实现Harness Engineering的协同关系**：
- Harness提供执行与监控的**基础设施**（Rules、Evals、Trace、Metrics）
- 评估系统提供分析与反馈的**决策能力**（轨迹评分、LLM Judge、评估报告）
- 两者协同形成**构建→执行→监控→评估→改进→构建**的完整闭环

