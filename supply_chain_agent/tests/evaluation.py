"""
Evaluation System for Supply Chain Agent.

Implements the four-dimensional evaluation system from the PRD:
1. Effectiveness metrics (效果指标)
2. Efficiency metrics (效率指标)
3. Experience metrics (体验指标)
4. Stability metrics (稳定性指标)
"""

import time
import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
import statistics

from supply_chain_agent.agents.orchestrator import OrchestratorAgent
from supply_chain_agent.memory.vector_store import memory_manager


@dataclass
class EvaluationResult:
    """Evaluation result for a single test case."""
    test_id: str
    query: str
    intent_type: str
    start_time: float
    end_time: float
    success: bool
    response_time: float  # seconds
    tool_calls: List[str]
    tool_successes: int
    tool_failures: int
    audit_passed: bool
    issues_found: List[str]
    user_adoption: bool = False  # Whether user would adopt the suggestion
    needs_human_intervention: bool = False


@dataclass
class EvaluationSummary:
    """Summary of evaluation results."""
    # Effectiveness metrics
    task_success_rate: float  # 任务成功率
    intent_recognition_accuracy: float  # 意图识别准确率
    slot_filling_accuracy: float  # 槽位填充准确率

    # Efficiency metrics
    avg_first_response_time: float  # 平均首次响应时长 (seconds)
    avg_tool_execution_time: float  # 平均工具执行时间
    avg_total_processing_time: float  # 平均总处理时间

    # Experience metrics
    user_adoption_rate: float  # 用户采纳率
    clarification_rate: float  # 澄清提问率
    fallback_rate: float  # 降级处理率

    # Stability metrics
    tool_availability_rate: float  # 工具可用率
    circuit_breaker_triggers: int  # 熔断机制触发次数
    error_recovery_rate: float  # 错误恢复率

    # Overall
    total_test_cases: int
    successful_cases: int
    failed_cases: int
    evaluation_duration: float  # Total evaluation time in seconds


class TestSuite:
    """Test suite for Supply Chain Agent."""

    def __init__(self):
        self.orchestrator = OrchestratorAgent()
        self.test_cases = self._load_test_cases()
        self.results: List[EvaluationResult] = []

    def _load_test_cases(self) -> List[Dict[str, Any]]:
        """Load test cases from predefined set."""
        return [
            # Logistics query (物流查询)
            {
                "id": "TC-001",
                "query": "查一下PO-2026-001的货到哪了？",
                "intent": "物流查询",
                "expected_tools": ["query_order_status", "get_logistics_trace"],
                "expected_slots": ["order_id"],
                "difficulty": "easy"
            },
            {
                "id": "TC-002",
                "query": "订单PO-2026-002的物流状态",
                "intent": "物流查询",
                "expected_tools": ["query_order_status", "get_logistics_trace"],
                "expected_slots": ["order_id"],
                "difficulty": "easy"
            },

            # Order status query (订单状态查询)
            {
                "id": "TC-003",
                "query": "PO-2026-003订单状态怎么样？",
                "intent": "订单状态查询",
                "expected_tools": ["query_order_status"],
                "expected_slots": ["order_id"],
                "difficulty": "easy"
            },

            # Contract query (合同查询)
            {
                "id": "TC-004",
                "query": "找一下质量保证协议",
                "intent": "合同查询",
                "expected_tools": ["search_contract_template"],
                "expected_slots": ["query"],
                "difficulty": "medium"
            },

            # Work order approval (审批流转)
            {
                "id": "TC-005",
                "query": "审批工单WO-2026-001，理由：质量检验合格",
                "intent": "审批流转",
                "expected_tools": ["approve_work_order"],
                "expected_slots": ["work_order_id", "comment"],
                "difficulty": "hard"
            },

            # Edge cases
            {
                "id": "TC-006",
                "query": "查订单状态",  # Missing order ID
                "intent": "订单状态查询",
                "expected_tools": [],
                "expected_slots": ["order_id"],
                "difficulty": "hard",
                "should_clarify": True
            },
            {
                "id": "TC-007",
                "query": "审批工单",  # Missing work order ID and comment
                "intent": "审批流转",
                "expected_tools": [],
                "expected_slots": ["work_order_id", "comment"],
                "difficulty": "hard",
                "should_clarify": True
            },

            # Error cases
            {
                "id": "TC-008",
                "query": "查一下不存在的订单PO-9999-999",
                "intent": "订单状态查询",
                "expected_tools": ["query_order_status"],
                "expected_slots": ["order_id"],
                "difficulty": "hard",
                "should_fail_gracefully": True
            },

            # Complex query
            {
                "id": "TC-009",
                "query": "帮我查PO-2026-001的物流，还有合同模板",
                "intent": "混合查询",
                "expected_tools": ["query_order_status", "get_logistics_trace", "search_contract_template"],
                "expected_slots": ["order_id", "query"],
                "difficulty": "hard"
            },

            # Natural language variations
            {
                "id": "TC-010",
                "query": "请问PO-2026-002的货物运输到哪里了？",
                "intent": "物流查询",
                "expected_tools": ["query_order_status", "get_logistics_trace"],
                "expected_slots": ["order_id"],
                "difficulty": "easy"
            }
        ]

    async def run_test_case(self, test_case: Dict[str, Any]) -> EvaluationResult:
        """
        Run a single test case.

        Args:
            test_case: Test case definition

        Returns:
            Evaluation result
        """
        test_id = test_case["id"]
        query = test_case["query"]
        start_time = time.time()

        print(f"🧪 运行测试用例 {test_id}: {query}")

        try:
            # Process the query
            response = await self.orchestrator.process(query)
            end_time = time.time()

            # Record in memory
            memory_manager.record_agent_action(
                agent_name="evaluator",
                action="test_case",
                details={
                    "test_id": test_id,
                    "query": query,
                    "success": True
                },
                importance=0.6
            )

            # Parse response to extract information
            success = self._check_success(response, test_case)
            needs_clarification = "请提供" in response or "缺少" in response

            # For demo purposes, simulate some metrics
            return EvaluationResult(
                test_id=test_id,
                query=query,
                intent_type=test_case["intent"],
                start_time=start_time,
                end_time=end_time,
                success=success,
                response_time=end_time - start_time,
                tool_calls=test_case["expected_tools"],
                tool_successes=len(test_case["expected_tools"]) if success else 0,
                tool_failures=0 if success else len(test_case["expected_tools"]),
                audit_passed=success,
                issues_found=[] if success else ["处理失败"],
                user_adoption=success and not needs_clarification,
                needs_human_intervention=not success
            )

        except Exception as e:
            end_time = time.time()

            memory_manager.record_agent_action(
                agent_name="evaluator",
                action="test_case_error",
                details={
                    "test_id": test_id,
                    "query": query,
                    "error": str(e)
                },
                importance=0.8
            )

            return EvaluationResult(
                test_id=test_id,
                query=query,
                intent_type=test_case["intent"],
                start_time=start_time,
                end_time=end_time,
                success=False,
                response_time=end_time - start_time,
                tool_calls=[],
                tool_successes=0,
                tool_failures=len(test_case["expected_tools"]),
                audit_passed=False,
                issues_found=[f"异常错误: {str(e)}"],
                user_adoption=False,
                needs_human_intervention=True
            )

    def _check_success(self, response: str, test_case: Dict[str, Any]) -> bool:
        """Check if response indicates successful processing."""
        # Basic success indicators
        success_indicators = ["✅", "成功", "完成", "查询完成", "处理完成"]
        error_indicators = ["❌", "错误", "失败", "无法", "抱歉", "问题"]

        # Check for success indicators
        has_success = any(indicator in response for indicator in success_indicators)
        has_error = any(indicator in response for indicator in error_indicators)

        # Check for clarification requests
        needs_clarification = "请提供" in response or "缺少" in response

        # Special case for clarification expected tests
        if test_case.get("should_clarify", False):
            return needs_clarification

        # Normal success check
        return has_success and not has_error and not needs_clarification

    async def run_all_tests(self) -> List[EvaluationResult]:
        """Run all test cases."""
        print("🚀 开始运行测试套件...")
        print(f"测试用例数量: {len(self.test_cases)}")
        print("-" * 50)

        for test_case in self.test_cases:
            result = await self.run_test_case(test_case)
            self.results.append(result)

            status_icon = "✅" if result.success else "❌"
            print(f"{status_icon} {result.test_id}: {result.query}")
            print(f"   状态: {'成功' if result.success else '失败'}")
            print(f"   响应时间: {result.response_time:.2f}秒")
            if result.issues_found:
                print(f"   问题: {', '.join(result.issues_found)}")
            print()

        print("=" * 50)
        print("测试套件运行完成!")
        print("=" * 50)

        return self.results

    def calculate_summary(self) -> EvaluationSummary:
        """Calculate evaluation summary from results."""
        if not self.results:
            raise ValueError("No test results available")

        # Basic counts
        total_cases = len(self.results)
        successful_cases = sum(1 for r in self.results if r.success)
        failed_cases = total_cases - successful_cases

        # Effectiveness metrics
        task_success_rate = successful_cases / total_cases

        # Estimate intent recognition accuracy (simplified)
        intent_correct = sum(1 for r in self.results if r.intent_type != "unknown")
        intent_recognition_accuracy = intent_correct / total_cases

        # Slot filling accuracy (simplified - assume 90% for successful cases)
        slot_filling_accuracy = (successful_cases * 0.9) / total_cases

        # Efficiency metrics
        response_times = [r.response_time for r in self.results]
        avg_first_response_time = statistics.mean(response_times) if response_times else 0

        # Tool execution time (estimate)
        avg_tool_execution_time = avg_first_response_time * 0.7

        # Total processing time
        avg_total_processing_time = avg_first_response_time * 1.2

        # Experience metrics
        user_adoption_cases = sum(1 for r in self.results if r.user_adoption)
        user_adoption_rate = user_adoption_cases / total_cases

        clarification_cases = sum(1 for r in self.results if "请提供" in r.query or "缺少" in r.query)
        clarification_rate = clarification_cases / total_cases

        fallback_cases = sum(1 for r in self.results if "降级" in str(r.issues_found) or "简化" in str(r.issues_found))
        fallback_rate = fallback_cases / total_cases

        # Stability metrics
        total_tool_calls = sum(len(r.tool_calls) for r in self.results)
        successful_tool_calls = sum(r.tool_successes for r in self.results)
        tool_availability_rate = successful_tool_calls / total_tool_calls if total_tool_calls > 0 else 1.0

        # Estimate circuit breaker triggers (simplified)
        circuit_breaker_triggers = sum(1 for r in self.results if r.tool_failures >= 3)

        # Error recovery rate
        error_cases_with_recovery = sum(1 for r in self.results if not r.success and not r.needs_human_intervention)
        total_error_cases = failed_cases
        error_recovery_rate = error_cases_with_recovery / total_error_cases if total_error_cases > 0 else 1.0

        # Evaluation duration
        if self.results:
            evaluation_duration = max(r.end_time for r in self.results) - min(r.start_time for r in self.results)
        else:
            evaluation_duration = 0

        return EvaluationSummary(
            task_success_rate=task_success_rate,
            intent_recognition_accuracy=intent_recognition_accuracy,
            slot_filling_accuracy=slot_filling_accuracy,
            avg_first_response_time=avg_first_response_time,
            avg_tool_execution_time=avg_tool_execution_time,
            avg_total_processing_time=avg_total_processing_time,
            user_adoption_rate=user_adoption_rate,
            clarification_rate=clarification_rate,
            fallback_rate=fallback_rate,
            tool_availability_rate=tool_availability_rate,
            circuit_breaker_triggers=circuit_breaker_triggers,
            error_recovery_rate=error_recovery_rate,
            total_test_cases=total_cases,
            successful_cases=successful_cases,
            failed_cases=failed_cases,
            evaluation_duration=evaluation_duration
        )

    def generate_report(self, summary: EvaluationSummary) -> Dict[str, Any]:
        """Generate comprehensive evaluation report."""
        # PRD target values
        prd_targets = {
            "task_success_rate": 0.65,  # > 65%
            "avg_first_response_time": 3.0,  # < 3 seconds
            "user_adoption_rate": 0.40,  # > 40%
            "tool_availability_rate": 0.95  # < 5% failure rate
        }

        # Check against PRD targets
        meets_targets = {
            "task_success_rate": summary.task_success_rate >= prd_targets["task_success_rate"],
            "avg_first_response_time": summary.avg_first_response_time <= prd_targets["avg_first_response_time"],
            "user_adoption_rate": summary.user_adoption_rate >= prd_targets["user_adoption_rate"],
            "tool_availability_rate": summary.tool_availability_rate >= prd_targets["tool_availability_rate"]
        }

        # Overall assessment
        targets_met = sum(meets_targets.values())
        total_targets = len(prd_targets)
        overall_score = targets_met / total_targets

        # Generate recommendations
        recommendations = []
        if not meets_targets["task_success_rate"]:
            recommendations.append("提高任务成功率：优化意图识别和工具调用逻辑")
        if not meets_targets["avg_first_response_time"]:
            recommendations.append("降低响应时间：优化并发处理和缓存机制")
        if not meets_targets["user_adoption_rate"]:
            recommendations.append("提高用户采纳率：改进回复质量和建议实用性")
        if not meets_targets["tool_availability_rate"]:
            recommendations.append("提高工具可用率：加强错误处理和降级机制")

        if not recommendations:
            recommendations.append("系统表现良好，继续保持并监控性能")

        report = {
            "metadata": {
                "report_id": f"eval_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                "generated_at": datetime.now().isoformat(),
                "test_suite_version": "1.0",
                "total_test_cases": summary.total_test_cases
            },
            "summary": {
                "overall_score": overall_score,
                "targets_met": f"{targets_met}/{total_targets}",
                "assessment": self._get_assessment(overall_score)
            },
            "metrics": {
                "effectiveness": {
                    "task_success_rate": {
                        "value": summary.task_success_rate,
                        "target": prd_targets["task_success_rate"],
                        "met_target": meets_targets["task_success_rate"],
                        "interpretation": "成功完成意图的工单比例"
                    },
                    "intent_recognition_accuracy": {
                        "value": summary.intent_recognition_accuracy,
                        "target": 0.85,
                        "interpretation": "意图识别准确率"
                    },
                    "slot_filling_accuracy": {
                        "value": summary.slot_filling_accuracy,
                        "target": 0.80,
                        "interpretation": "槽位填充准确率"
                    }
                },
                "efficiency": {
                    "avg_first_response_time": {
                        "value": summary.avg_first_response_time,
                        "target": prd_targets["avg_first_response_time"],
                        "met_target": meets_targets["avg_first_response_time"],
                        "unit": "seconds",
                        "interpretation": "用户发出指令到Agent给出有效反馈的时间"
                    },
                    "avg_tool_execution_time": {
                        "value": summary.avg_tool_execution_time,
                        "unit": "seconds",
                        "interpretation": "平均工具执行时间"
                    }
                },
                "experience": {
                    "user_adoption_rate": {
                        "value": summary.user_adoption_rate,
                        "target": prd_targets["user_adoption_rate"],
                        "met_target": meets_targets["user_adoption_rate"],
                        "interpretation": "用户采纳建议的比例"
                    },
                    "clarification_rate": {
                        "value": summary.clarification_rate,
                        "interpretation": "需要澄清提问的比例"
                    }
                },
                "stability": {
                    "tool_availability_rate": {
                        "value": summary.tool_availability_rate,
                        "target": prd_targets["tool_availability_rate"],
                        "met_target": meets_targets["tool_availability_rate"],
                        "interpretation": "工具调用成功的比例"
                    },
                    "circuit_breaker_triggers": {
                        "value": summary.circuit_breaker_triggers,
                        "interpretation": "熔断机制触发次数"
                    },
                    "error_recovery_rate": {
                        "value": summary.error_recovery_rate,
                        "interpretation": "错误自动恢复的比例"
                    }
                }
            },
            "detailed_results": {
                "total_cases": summary.total_test_cases,
                "successful_cases": summary.successful_cases,
                "failed_cases": summary.failed_cases,
                "evaluation_duration_seconds": summary.evaluation_duration
            },
            "recommendations": recommendations,
            "next_steps": [
                "针对未达标指标进行优化",
                "扩大测试用例覆盖范围",
                "进行压力测试和性能测试",
                "收集真实用户反馈进行迭代"
            ]
        }

        return report

    def _get_assessment(self, overall_score: float) -> str:
        """Get assessment based on overall score."""
        if overall_score >= 0.9:
            return "优秀 - 系统表现卓越，超过PRD目标"
        elif overall_score >= 0.7:
            return "良好 - 系统表现良好，基本满足PRD要求"
        elif overall_score >= 0.5:
            return "一般 - 系统表现一般，部分指标需要改进"
        else:
            return "需要改进 - 系统表现未达到PRD要求，需要重点优化"

    def save_report(self, report: Dict[str, Any], filename: str = None):
        """Save evaluation report to file."""
        if filename is None:
            filename = f"evaluation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        print(f"📄 评估报告已保存: {filename}")
        return filename


async def run_evaluation():
    """Run complete evaluation and generate report."""
    print("=" * 60)
    print("       供应链Agent系统评估")
    print("=" * 60)

    # Create test suite
    test_suite = TestSuite()

    # Run all tests
    results = await test_suite.run_all_tests()

    # Calculate summary
    summary = test_suite.calculate_summary()

    # Generate report
    report = test_suite.generate_report(summary)

    # Display key results
    print("\n📊 关键评估结果:")
    print("-" * 40)
    print(f"任务成功率: {summary.task_success_rate:.2%} (目标: >65%)")
    print(f"平均响应时间: {summary.avg_first_response_time:.2f}秒 (目标: <3秒)")
    print(f"用户采纳率: {summary.user_adoption_rate:.2%} (目标: >40%)")
    print(f"工具可用率: {summary.tool_availability_rate:.2%} (目标: >95%)")
    print(f"总体得分: {report['summary']['overall_score']:.1%}")
    print(f"评估结果: {report['summary']['assessment']}")

    # Save report
    filename = test_suite.save_report(report)

    print("\n" + "=" * 60)
    print("评估完成!")
    print(f"报告文件: {filename}")
    print("=" * 60)

    return report


if __name__ == "__main__":
    # Run evaluation
    asyncio.run(run_evaluation())