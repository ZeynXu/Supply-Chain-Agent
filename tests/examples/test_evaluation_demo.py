"""
评估系统测试示例

演示如何使用评估系统的各个模块进行测试。
运行方式: python tests/examples/test_evaluation_demo.py
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path

# 添加项目路径
import sys
sys.path.insert(0, '/root/Supply-Chain-Agent')


async def demo_trajectory_scorer():
    """演示轨迹评分器"""
    print("\n" + "="*60)
    print("【轨迹评分器测试】")
    print("="*60)

    from supply_chain_agent.evaluation import (
        TrajectoryScorer,
        EvalContext,
        GoldResult,
    )

    # 创建评分器
    scorer = TrajectoryScorer()

    # 构建模拟上下文
    context = EvalContext(
        thread_id="demo_001",
        user_query="查询客户C001的订单信息",
        intent={"intent_level_1": "信息查询", "intent_level_2": "订单查询"},
        tool_calls=[
            {"tool_name": "query_order", "params": {"customer_id": "C001"}, "success": True}
        ],
        audit_results={"issues": [], "warnings": []},
        final_response="客户C001共有3个订单，最近的订单号为O12345...",
        status="ok",
        latency_ms=850
    )

    # 构建黄金标准
    gold = GoldResult(
        expected_intent={"intent_level_1": "信息查询", "intent_level_2": "订单查询"},
        expected_tools=["query_order"],
        expected_response_keywords=["订单", "C001"],
        expected_violations=[]
    )

    # 执行评分
    result = await scorer.score("demo_001", gold, context)

    print(f"\n综合得分: {result.overall_score:.3f}")
    print(f"是否通过: {result.overall_score >= 0.75}")
    print("\n各维度评分:")
    for ds in result.dimension_scores:
        status = "✅" if ds.passed else "❌"
        print(f"  {status} {ds.dimension}: {ds.score:.3f} (权重: {ds.weight})")
        if ds.message:
            print(f"      说明: {ds.message}")


async def demo_llm_judge():
    """演示LLM Judge"""
    print("\n" + "="*60)
    print("【LLM Judge测试】")
    print("="*60)

    from supply_chain_agent.evaluation import LLMJudge
    from supply_chain_agent.evaluation.config import LLMJudgeConfig

    # 创建LLM Judge（使用默认配置：GLM-4-flash）
    config = LLMJudgeConfig()
    judge = LLMJudge(config)

    # 模拟评估
    user_query = "查询订单O12345的配送状态"
    agent_response = "订单O12345目前正在配送中，预计明天下午送达。配送员张三，联系电话138****1234。"

    print(f"\n用户查询: {user_query}")
    print(f"Agent响应: {agent_response}")
    print("\n正在调用LLM Judge评分...")

    # 执行评分
    result = await judge.score(user_query, agent_response)

    print(f"\n评分结果:")
    print(f"  帮助性: {result.helpfulness}/5")
    print(f"  清晰度: {result.clarity}/5")
    print(f"  忠实度: {result.faithfulness}/5")
    print(f"  平均分: {result.average_score():.2f}/5")
    print(f"  置信度: {result.confidence:.2f}")
    print(f"  理由: {result.reasoning}")


async def demo_tool_call_validator():
    """演示工具调用验证器"""
    print("\n" + "="*60)
    print("【工具调用验证器测试】")
    print("="*60)

    from supply_chain_agent.evaluation import (
        ToolCallValidator,
        ToolCallActual,
        ToolCallGold,
    )

    validator = ToolCallValidator()

    # 测试用例1：正确的工具调用
    print("\n测试用例1: 正确的工具调用")
    actual = ToolCallActual(
        tool_name="query_order",
        params={"order_id": "O12345"},
        success=True
    )
    gold = ToolCallGold(
        should_call_tool=True,
        expected_tool="query_order",
        expected_params={"order_id": "O12345"}
    )
    result = validator.evaluate(actual, gold)
    print(f"  综合得分: {result.overall_score:.3f}")
    print(f"  决策正确: {result.decision_correct}")
    print(f"  工具正确: {result.tool_correct}")

    # 测试用例2：错误的工具调用
    print("\n测试用例2: 错误的工具调用")
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
    print(f"  综合得分: {result.overall_score:.3f}")
    print(f"  决策正确: {result.decision_correct}")
    print(f"  工具正确: {result.tool_correct}")

    # 测试用例3：不应该调用工具
    print("\n测试用例3: 不应该调用工具（闲聊场景）")
    actual = ToolCallActual(
        tool_name="",
        params={},
        success=True
    )
    gold = ToolCallGold(
        should_call_tool=False,
        expected_tool=None
    )
    result = validator.evaluate(actual, gold)
    print(f"  综合得分: {result.overall_score:.3f}")
    print(f"  决策正确: {result.decision_correct}")


async def demo_eval_runner():
    """演示评估运行器"""
    print("\n" + "="*60)
    print("【评估运行器测试】")
    print("="*60)

    from supply_chain_agent.evaluation import (
        EvalRunner,
        EvalRunnerConfig,
        EvalContext,
        GoldResult,
    )

    # 创建运行器
    runner_config = EvalRunnerConfig(
        include_trajectory=True,
        include_quality=True,
        include_tool_validation=True
    )
    runner = EvalRunner(runner_config=runner_config)

    # 构建模拟评估
    context = EvalContext(
        thread_id="runner_demo_001",
        user_query="创建一个紧急工单",
        intent={"intent_level_1": "工单管理", "intent_level_2": "创建工单"},
        tool_calls=[
            {"tool_name": "create_work_order", "params": {"customer_id": "C001", "priority": "high"}, "success": True}
        ],
        audit_results={"issues": [], "warnings": []},
        final_response="已成功创建紧急工单，工单号为WO12345...",
        status="ok",
        latency_ms=1200
    )

    gold = GoldResult(
        expected_intent={"intent_level_1": "工单管理", "intent_level_2": "创建工单"},
        expected_tools=["create_work_order"],
        expected_response_keywords=["工单", "创建成功"],
        expected_violations=[]
    )

    # 执行评估
    result = await runner.evaluate_thread("runner_demo_001", gold, context)

    print(f"\n评估结果:")
    print(f"  整体通过: {'✅ 是' if result.overall_passed else '❌ 否'}")
    print(f"  轨迹评分: {result.trajectory_score.overall_score:.3f}")

    if result.quality_score:
        print(f"  质量评分: {result.quality_score.average_score():.2f}/5")

    print(f"\n统计信息:")
    stats = runner.get_stats()
    print(f"  总评估数: {stats['total_evaluated']}")
    print(f"  通过率: {stats['pass_rate']:.2%}")


async def demo_eval_report():
    """演示评估报告生成"""
    print("\n" + "="*60)
    print("【评估报告生成测试】")
    print("="*60)

    from supply_chain_agent.evaluation import (
        EvaluationReporter,
        FullEvaluation,
        TrajectoryScore,
        DimensionScore,
        QualityScore,
    )
    from supply_chain_agent.evaluation.core.trajectory_scorer import ALL_DIMENSIONS

    # 创建报告生成器
    reporter = EvaluationReporter()

    # 构建模拟评估结果
    evaluations = []
    for i in range(5):
        eval_result = FullEvaluation(
            thread_id=f"test_{i:03d}",
            trajectory_score=TrajectoryScore(
                trace_id=f"test_{i:03d}",
                overall_score=0.75 + i * 0.05,
                dimension_scores=[
                    DimensionScore(dimension=d, score=0.7 + i * 0.05, weight=0.11, passed=True)
                    for d in ALL_DIMENSIONS
                ]
            ),
            quality_score=QualityScore(
                helpfulness=3.5 + i * 0.3,
                clarity=4.0,
                faithfulness=4.5,
                reasoning="模拟评分",
                confidence=0.8
            ),
            overall_passed=i >= 2
        )
        evaluations.append(eval_result)

    # 生成报告
    report = reporter.generate_report(evaluations, "2026-W24 Demo测试")

    print("\n生成的报告预览:")
    print("-" * 40)
    # 只显示报告前50行
    lines = report.split('\n')[:50]
    print('\n'.join(lines))
    if len(report.split('\n')) > 50:
        print("\n... (报告已截断)")


async def demo_harness_integration():
    """演示Harness集成"""
    print("\n" + "="*60)
    print("【Harness集成测试】")
    print("="*60)

    from supply_chain_agent.evaluation import (
        get_rules_integration,
        get_evals_integration,
        get_error_cluster_integration,
    )

    # 测试Rules集成
    print("\n1. Harness Rules集成:")
    rules = get_rules_integration()
    print(f"   可用状态: {'✅ 可用' if rules.is_available() else '❌ 不可用'}")

    if rules.is_available():
        all_rules = rules.get_all_rules()
        print(f"   已加载规则数: {len(all_rules)}")

    # 测试Evals集成
    print("\n2. Harness Evals集成:")
    evals = get_evals_integration()
    print(f"   集成对象: ✅ 已创建")

    # 测试错误聚类集成
    print("\n3. 错误聚类集成:")
    error_cluster = get_error_cluster_integration()
    print(f"   集成对象: ✅ 已创建")

    # 获取Top错误模式（如果数据存在）
    try:
        top_errors = error_cluster.get_top_error_patterns(days=7, limit=3)
        if top_errors:
            print(f"   Top错误模式:")
            for i, err in enumerate(top_errors, 1):
                print(f"     {i}. {err.get('error_type', 'Unknown')}: {err.get('count', 0)}次")
        else:
            print(f"   暂无错误数据（需要生产环境Trace数据）")
    except Exception as e:
        print(f"   获取错误数据失败: {e}")


async def demo_golden_samples():
    """演示黄金样本"""
    print("\n" + "="*60)
    print("【黄金样本测试】")
    print("="*60)

    from supply_chain_agent.evaluation.datasets import load_golden_samples

    samples = load_golden_samples()

    print(f"\n黄金样本总数: {len(samples)}")

    # 按类别统计
    categories = {}
    for s in samples:
        cat = s.get("category", "unknown")
        categories[cat] = categories.get(cat, 0) + 1

    print("\n类别分布:")
    for cat, count in sorted(categories.items()):
        print(f"  {cat}: {count}个")

    # 按难度统计
    difficulties = {}
    for s in samples:
        diff = s.get("difficulty", "unknown")
        difficulties[diff] = difficulties.get(diff, 0) + 1

    print("\n难度分布:")
    for diff, count in sorted(difficulties.items()):
        print(f"  {diff}: {count}个")

    # 显示几个样本
    print("\n样本示例:")
    for s in samples[:3]:
        print(f"\n  [{s['sample_id']}] {s['user_query']}")
        print(f"    期望意图: {s['gold_result']['expected_intent']}")
        print(f"    期望工具: {s['gold_result']['expected_tools']}")


async def demo_metrics_export():
    """演示指标导出"""
    print("\n" + "="*60)
    print("【Prometheus指标导出测试】")
    print("="*60)

    from supply_chain_agent.evaluation.monitoring import (
        record_eval_run,
        record_trajectory_score,
        record_trajectory_overall,
        record_quality_score,
        set_eval_pass_rate,
    )

    # 模拟记录指标
    print("\n记录评估指标...")

    # 记录评估运行
    record_eval_run("full", "passed")
    record_eval_run("full", "passed")
    record_eval_run("full", "failed")

    # 记录轨迹评分
    record_trajectory_overall(0.85)
    record_trajectory_score("tool_selection", 0.9)
    record_trajectory_score("params_complete", 0.85)
    record_trajectory_score("latency", 0.95)

    # 记录质量评分
    record_quality_score("helpfulness", 4.5)
    record_quality_score("clarity", 4.0)
    record_quality_score("faithfulness", 4.8)

    # 设置通过率
    set_eval_pass_rate(0.85)

    print("✅ 指标已记录到Prometheus Registry")
    print("\n提示: 可通过 /metrics 端点查看指标")


async def demo_dashboard():
    """演示监控仪表盘"""
    print("\n" + "="*60)
    print("【监控仪表盘测试】")
    print("="*60)

    from supply_chain_agent.evaluation import EvalDashboard

    # 创建仪表盘
    dashboard = EvalDashboard(enable_error_cluster=True)

    print("\n仪表盘配置:")
    print(f"  Trace目录: {dashboard.trace_dir}")
    print(f"  日志目录: {dashboard.log_dir}")
    print(f"  错误聚类集成: {'✅ 启用' if dashboard.enable_error_cluster else '❌ 禁用'}")

    # 获取仪表盘数据
    print("\n获取仪表盘数据...")
    try:
        data = await dashboard.get_dashboard_data("24h")
        print(f"  总请求数: {data.total_requests}")
        print(f"  成功率: {data.success_rate:.2%}")
        print(f"  平均延迟: {data.avg_latency_ms:.0f}ms")
        print(f"  P99延迟: {data.p99_latency_ms:.0f}ms")

        if data.alerts:
            print(f"\n告警 ({len(data.alerts)}条):")
            for alert in data.alerts[:3]:
                print(f"  ⚠️ {alert['type']}: {alert['message']}")

        if data.improvement_suggestions:
            print(f"\n改进建议:")
            for sug in data.improvement_suggestions[:3]:
                print(f"  - {sug}")

    except Exception as e:
        print(f"  获取数据失败: {e}")
        print("  (可能需要生产环境Trace数据)")


async def main():
    """运行所有演示"""
    print("\n" + "="*60)
    print("Agent评估系统测试演示")
    print(f"运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)

    # 运行各个演示
    await demo_trajectory_scorer()
    await demo_tool_call_validator()
    await demo_eval_runner()
    await demo_llm_judge()
    await demo_eval_report()
    await demo_harness_integration()
    await demo_golden_samples()
    await demo_metrics_export()
    await demo_dashboard()

    print("\n" + "="*60)
    print("演示完成!")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())
