"""
评估系统测试

验证核心功能是否正常工作。
"""

import pytest
from datetime import datetime

from supply_chain_agent.evaluation import (
    EvalConfig,
    LLMJudgeConfig,
    TrajectoryScorer,
    ToolCallValidator,
    EvalRunner,
    EvaluationReporter,
    TrajectoryScore,
    DimensionScore,
    QualityScore,
    EvalContext,
    GoldResult,
    GoldenSample,
    ToolCallActual,
    ToolCallGold,
)


class TestEvalConfig:
    """测试评估配置"""

    def test_default_config(self):
        """测试默认配置"""
        config = EvalConfig.get_default()

        assert config.enabled is True
        assert config.trajectory_weights.tool_selection == 0.15
        assert config.thresholds.trajectory_pass == 0.75

    def test_llm_judge_config(self):
        """测试LLM Judge配置"""
        config = LLMJudgeConfig()

        assert config.provider == "zhipu"
        assert config.model == "glm-4-flash"
        assert config.temperature == 0.1

    def test_config_to_dict(self):
        """测试配置序列化"""
        config = EvalConfig.get_default()
        data = config.to_dict()

        assert "trajectory_weights" in data
        assert "thresholds" in data
        assert "llm_judge" in data


class TestTrajectoryScorer:
    """测试轨迹评分器"""

    def test_scorer_initialization(self):
        """测试初始化"""
        config = EvalConfig.get_default()
        scorer = TrajectoryScorer(config)

        assert scorer.config is not None
        assert scorer.weights is not None

    def test_dimension_scores(self):
        """测试维度评分"""
        config = EvalConfig.get_default()
        scorer = TrajectoryScorer(config)

        # 构建模拟上下文
        context = EvalContext(
            thread_id="test_001",
            user_query="查询订单",
            tool_calls=[
                {"tool_name": "query_order", "params": {"order_id": "O001"}, "success": True}
            ],
            final_response="订单O001的信息如下...",
            status="ok",
            latency_ms=500
        )

        # 测试各维度评分方法
        ds_tool = scorer._score_tool_selection(context, None)
        assert ds_tool.dimension == "tool_selection"
        assert 0 <= ds_tool.score <= 1

        ds_latency = scorer._score_latency(context)
        assert ds_latency.dimension == "latency"
        assert 0 <= ds_latency.score <= 1


class TestToolCallValidator:
    """测试工具调用验证器"""

    def test_validator_initialization(self):
        """测试初始化"""
        validator = ToolCallValidator()
        assert validator.config is not None

    def test_validate_correct_call(self):
        """测试正确的工具调用"""
        validator = ToolCallValidator()

        actual = ToolCallActual(
            tool_name="query_order",
            params={"order_id": "O001"},
            success=True
        )

        gold = ToolCallGold(
            should_call_tool=True,
            expected_tool="query_order",
            expected_params={"order_id": "O001"}
        )

        result = validator.evaluate(actual, gold)

        assert result.tool_correct is True
        assert result.overall_score > 0.8

    def test_validate_wrong_tool(self):
        """测试错误的工具调用"""
        validator = ToolCallValidator()

        actual = ToolCallActual(
            tool_name="query_customer",
            params={"customer_id": "C001"},
            success=True
        )

        gold = ToolCallGold(
            should_call_tool=True,
            expected_tool="query_order",
            expected_params={}
        )

        result = validator.evaluate(actual, gold)

        assert result.tool_correct is False
        # 工具选择错误但决策正确(应该调用工具)，所以得分是 1.0*0.30 + 0.0*0.25 + 1.0*0.25 + 1.0*0.20 = 0.75
        assert result.overall_score == 0.75


class TestQualityScore:
    """测试质量评分"""

    def test_quality_score_creation(self):
        """测试创建质量评分"""
        score = QualityScore(
            helpfulness=4.5,
            clarity=4.0,
            faithfulness=5.0,
            reasoning="响应清晰有帮助",
            confidence=0.9
        )

        assert score.helpfulness == 4.5
        assert score.average_score() == pytest.approx(4.5, 0.1)

    def test_quality_score_to_labels(self):
        """测试标签转换"""
        score = QualityScore(
            helpfulness=4.5,
            clarity=3.5,
            faithfulness=2.0,
            reasoning="",
            confidence=0.8
        )

        labels = score.to_labels()

        assert labels["helpfulness"] == "excellent"
        assert labels["clarity"] == "good"
        # faithfulness=2.0 < 2.5, 所以是 "poor"
        assert labels["faithfulness"] == "poor"


class TestEvalRunner:
    """测试评估运行器"""

    def test_runner_initialization(self):
        """测试初始化"""
        runner = EvalRunner()

        assert runner.config is not None
        assert runner.trajectory_scorer is not None
        assert runner.llm_judge is not None

    def test_runner_stats(self):
        """测试统计信息"""
        runner = EvalRunner()
        stats = runner.get_stats()

        assert "total_evaluated" in stats
        assert "pass_rate" in stats


class TestEvaluationReporter:
    """测试评估报告生成器"""

    def test_reporter_initialization(self):
        """测试初始化"""
        reporter = EvaluationReporter()

        assert reporter.config is not None
        assert reporter.output_dir is not None

    def test_generate_empty_report(self):
        """测试生成空报告"""
        reporter = EvaluationReporter()
        report = reporter.generate_report([], "2026-W24", "测试报告")

        assert "测试报告" in report
        assert "2026-W24" in report
        assert "无评估数据" in report


class TestDimensionScore:
    """测试维度评分"""

    def test_dimension_score_creation(self):
        """测试创建维度评分"""
        ds = DimensionScore(
            dimension="tool_selection",
            score=0.85,
            weight=0.15,
            passed=True,
            message="工具选择正确"
        )

        assert ds.dimension == "tool_selection"
        assert ds.score == 0.85
        assert ds.to_dict()["score"] == 0.85


class TestGoldenSample:
    """测试黄金样本"""

    def test_golden_sample_creation(self):
        """测试创建黄金样本"""
        sample = GoldenSample(
            sample_id="test_001",
            user_query="查询订单O001",
            gold_result=GoldResult(
                expected_intent={"intent_level_1": "信息查询", "intent_level_2": "订单查询"},
                expected_tools=["query_order"],
                expected_response_keywords=["订单"],
                expected_violations=[]
            ),
            category="intent",
            difficulty="easy"
        )

        assert sample.sample_id == "test_001"
        assert sample.category == "intent"

    def test_golden_sample_to_dict(self):
        """测试序列化"""
        sample = GoldenSample(
            sample_id="test_001",
            user_query="查询订单O001",
            gold_result=GoldResult(
                expected_intent={},
                expected_tools=[],
                expected_response_keywords=[],
                expected_violations=[]
            )
        )

        data = sample.to_dict()

        assert "sample_id" in data
        assert "gold_result" in data


class TestHarnessIntegration:
    """测试Harness集成"""

    def test_rules_integration(self):
        """测试Rules集成"""
        from supply_chain_agent.evaluation import (
            HarnessRulesIntegration,
            get_rules_integration,
        )

        integration = get_rules_integration()
        assert integration is not None
        # 检查是否可用（取决于Harness是否已配置）
        available = integration.is_available()
        assert isinstance(available, bool)

    def test_evals_integration(self):
        """测试Evals集成"""
        from supply_chain_agent.evaluation import (
            HarnessEvalsIntegration,
            get_evals_integration,
        )

        integration = get_evals_integration()
        assert integration is not None

    def test_error_cluster_integration(self):
        """测试错误聚类集成"""
        from supply_chain_agent.evaluation import (
            HarnessErrorClusterIntegration,
            get_error_cluster_integration,
        )

        integration = get_error_cluster_integration()
        assert integration is not None

    def test_trajectory_scorer_with_harness_rules(self):
        """测试轨迹评分器集成Harness Rules"""
        from supply_chain_agent.evaluation import TrajectoryScorer

        # 创建启用Harness Rules的评分器
        scorer = TrajectoryScorer(use_harness_rules=True)
        assert scorer.use_harness_rules is True

        # 创建不使用Harness Rules的评分器
        scorer_no_harness = TrajectoryScorer(use_harness_rules=False)
        assert scorer_no_harness.use_harness_rules is False


class TestMetricsExporter:
    """测试指标导出"""

    def test_record_eval_run(self):
        """测试记录评估运行"""
        from supply_chain_agent.evaluation.monitoring import record_eval_run

        # 应该不会抛出异常
        record_eval_run("full", "passed")
        record_eval_run("full", "failed")

    def test_record_trajectory_score(self):
        """测试记录轨迹评分"""
        from supply_chain_agent.evaluation.monitoring import (
            record_trajectory_score,
            record_trajectory_overall,
        )

        record_trajectory_score("tool_selection", 0.85)
        record_trajectory_overall(0.78)

    def test_record_quality_score(self):
        """测试记录质量评分"""
        from supply_chain_agent.evaluation.monitoring import record_quality_score

        record_quality_score("helpfulness", 4.5)
        record_quality_score("clarity", 4.0)


class TestGoldenSamples:
    """测试黄金样本集"""

    def test_load_golden_samples(self):
        """测试加载黄金样本"""
        from supply_chain_agent.evaluation.datasets import load_golden_samples

        samples = load_golden_samples()

        assert isinstance(samples, list)
        assert len(samples) >= 5  # 至少5个样本

    def test_golden_samples_structure(self):
        """测试黄金样本结构"""
        from supply_chain_agent.evaluation.datasets import load_golden_samples

        samples = load_golden_samples()

        for sample in samples:
            assert "sample_id" in sample
            assert "user_query" in sample
            assert "gold_result" in sample
            assert "expected_intent" in sample["gold_result"]


class TestEvalRunnerWithHarness:
    """测试EvalRunner与Harness集成"""

    def test_runner_with_harness_evals(self):
        """测试Runner集成Harness Evals"""
        from supply_chain_agent.evaluation import EvalRunner, EvalRunnerConfig

        config = EvalRunnerConfig(include_harness_evals=True)
        runner = EvalRunner(runner_config=config)

        assert runner.runner_config.include_harness_evals is True

    def test_runner_set_agents(self):
        """测试设置Agents"""
        from supply_chain_agent.evaluation import EvalRunner

        runner = EvalRunner()
        runner.set_agents({"parser": None, "executor": None})

        assert "parser" in runner.agents
        assert "executor" in runner.agents


class TestEvalDashboardWithCluster:
    """测试仪表盘集成错误聚类"""

    def test_dashboard_with_error_cluster(self):
        """测试仪表盘启用错误聚类"""
        from supply_chain_agent.evaluation import EvalDashboard

        dashboard = EvalDashboard(enable_error_cluster=True)
        assert dashboard.enable_error_cluster is True

    def test_dashboard_without_error_cluster(self):
        """测试仪表盘禁用错误聚类"""
        from supply_chain_agent.evaluation import EvalDashboard

        dashboard = EvalDashboard(enable_error_cluster=False)
        assert dashboard.enable_error_cluster is False
