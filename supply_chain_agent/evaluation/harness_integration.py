"""
Harness集成模块

提供与Harness各组件的集成接口。
"""

import logging
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)


class HarnessRulesIntegration:
    """
    Harness Rules集成

    封装对harness/rules/evaluator.py的调用。
    """

    def __init__(self):
        """初始化"""
        self._rule_loader = None
        self._rule_evaluator = None
        self._initialized = False

    def _ensure_initialized(self):
        """确保已初始化"""
        if self._initialized:
            return

        try:
            from supply_chain_agent.harness.rules.loader import RuleLoader
            from supply_chain_agent.harness.rules.evaluator import RuleEvaluator

            self._rule_loader = RuleLoader()
            self._rule_evaluator = RuleEvaluator(self._rule_loader)
            self._initialized = True
            logger.info("Harness Rules集成初始化成功")
        except ImportError as e:
            logger.warning(f"Harness Rules模块不可用: {e}")
            self._initialized = True  # 标记为已尝试初始化
        except Exception as e:
            logger.error(f"Harness Rules初始化失败: {e}")
            self._initialized = True

    def evaluate_rules(
        self,
        context: Dict[str, Any]
    ) -> Tuple[List[Any], List[Any], List[Any]]:
        """
        评估业务规则

        Args:
            context: 评估上下文，包含 work_order, order, customer 等

        Returns:
            (issues, warnings, notifications) 三元组
        """
        self._ensure_initialized()

        if self._rule_evaluator is None:
            return [], [], []

        try:
            return self._rule_evaluator.evaluate_all(context)
        except Exception as e:
            logger.error(f"规则评估失败: {e}")
            return [], [], []

    def evaluate_single_rule(
        self,
        rule_id: str,
        context: Dict[str, Any]
    ) -> Optional[Any]:
        """
        评估单个规则

        Args:
            rule_id: 规则ID
            context: 评估上下文

        Returns:
            评估结果
        """
        self._ensure_initialized()

        if self._rule_evaluator is None:
            return None

        try:
            return self._rule_evaluator.evaluate_rule(rule_id, context)
        except Exception as e:
            logger.error(f"规则 '{rule_id}' 评估失败: {e}")
            return None

    def get_all_rules(self) -> List[Any]:
        """获取所有规则"""
        self._ensure_initialized()

        if self._rule_loader is None:
            return []

        try:
            return self._rule_loader.get_all_rules()
        except Exception as e:
            logger.error(f"获取规则列表失败: {e}")
            return []

    def is_available(self) -> bool:
        """检查是否可用"""
        self._ensure_initialized()
        return self._rule_evaluator is not None


class HarnessEvalsIntegration:
    """
    Harness Evals集成

    封装对harness/evals/的调用。
    """

    def __init__(self):
        """初始化"""
        self._initialized = False

    def _ensure_initialized(self):
        """确保已初始化"""
        if self._initialized:
            return
        self._initialized = True

    async def run_intent_eval(
        self,
        parser_agent,
        test_cases: List[Dict[str, Any]]
    ) -> List[Any]:
        """
        运行意图识别评估

        Args:
            parser_agent: Parser Agent实例
            test_cases: 测试用例列表

        Returns:
            评估结果列表
        """
        self._ensure_initialized()

        try:
            from supply_chain_agent.harness.evals.intent_eval import (
                IntentAccuracyEvaluator,
                IntentConfidenceEvaluator
            )
            from supply_chain_agent.harness.evals.base import EvalSuite

            suite = EvalSuite("intent_evaluation")
            suite.add_evaluator(IntentAccuracyEvaluator(parser_agent))
            suite.add_evaluator(IntentConfidenceEvaluator(parser_agent))

            return await suite.run_all(test_cases)
        except ImportError as e:
            logger.warning(f"Harness Evals模块不可用: {e}")
            return []
        except Exception as e:
            logger.error(f"意图评估失败: {e}")
            return []

    async def run_tool_eval(
        self,
        executor_agent,
        test_cases: List[Dict[str, Any]]
    ) -> List[Any]:
        """
        运行工具调用评估

        Args:
            executor_agent: Executor Agent实例
            test_cases: 测试用例列表

        Returns:
            评估结果列表
        """
        self._ensure_initialized()

        try:
            from supply_chain_agent.harness.evals.tool_eval import (
                ToolCallAccuracyEvaluator,
                ToolParamValidationEvaluator
            )
            from supply_chain_agent.harness.evals.base import EvalSuite

            suite = EvalSuite("tool_evaluation")
            suite.add_evaluator(ToolCallAccuracyEvaluator(executor_agent))
            suite.add_evaluator(ToolParamValidationEvaluator(executor_agent))

            return await suite.run_all(test_cases)
        except ImportError as e:
            logger.warning(f"Harness Evals模块不可用: {e}")
            return []
        except Exception as e:
            logger.error(f"工具评估失败: {e}")
            return []

    async def run_e2e_eval(
        self,
        orchestrator_agent,
        test_cases: List[Dict[str, Any]]
    ) -> List[Any]:
        """
        运行端到端评估

        Args:
            orchestrator_agent: Orchestrator Agent实例
            test_cases: 测试用例列表

        Returns:
            评估结果列表
        """
        self._ensure_initialized()

        try:
            from supply_chain_agent.harness.evals.e2e_eval import (
                E2EWorkflowEvaluator,
                E2ELatencyEvaluator
            )
            from supply_chain_agent.harness.evals.base import EvalSuite

            suite = EvalSuite("e2e_evaluation")
            suite.add_evaluator(E2EWorkflowEvaluator(orchestrator_agent))
            suite.add_evaluator(E2ELatencyEvaluator(orchestrator_agent))

            return await suite.run_all(test_cases)
        except ImportError as e:
            logger.warning(f"Harness Evals模块不可用: {e}")
            return []
        except Exception as e:
            logger.error(f"端到端评估失败: {e}")
            return []

    async def run_audit_eval(
        self,
        auditor_agent,
        test_cases: List[Dict[str, Any]]
    ) -> List[Any]:
        """
        运行审计规则评估

        Args:
            auditor_agent: Auditor Agent实例
            test_cases: 测试用例列表

        Returns:
            评估结果列表
        """
        self._ensure_initialized()

        try:
            from supply_chain_agent.harness.evals.audit_eval import (
                AuditRuleCoverageEvaluator,
                RiskScoreEvaluator
            )
            from supply_chain_agent.harness.evals.base import EvalSuite

            suite = EvalSuite("audit_evaluation")
            suite.add_evaluator(AuditRuleCoverageEvaluator(auditor_agent))
            suite.add_evaluator(RiskScoreEvaluator(auditor_agent))

            return await suite.run_all(test_cases)
        except ImportError as e:
            logger.warning(f"Harness Evals模块不可用: {e}")
            return []
        except Exception as e:
            logger.error(f"审计评估失败: {e}")
            return []


class HarnessErrorClusterIntegration:
    """
    Harness错误聚类集成

    封装对harness/feedback/cluster_errors.py的调用。
    """

    def __init__(self, log_dir: str = None, trace_dir: str = None):
        """初始化"""
        self.log_dir = log_dir
        self.trace_dir = trace_dir
        self._initialized = False

    def _ensure_initialized(self):
        """确保已初始化"""
        if self._initialized:
            return
        self._initialized = True

    def analyze_errors(self, days: int = 7) -> Dict[str, Any]:
        """
        分析错误

        Args:
            days: 分析天数

        Returns:
            错误聚类报告
        """
        self._ensure_initialized()

        try:
            from supply_chain_agent.harness.feedback.cluster_errors import ErrorCluster

            cluster = ErrorCluster(
                log_dir=self.log_dir or "/root/Supply-Chain-Agent/logs",
                trace_dir=self.trace_dir or "/root/autodl-tmp/harness-traces"
            )

            return cluster.analyze(days)
        except ImportError as e:
            logger.warning(f"Harness错误聚类模块不可用: {e}")
            return {"total_errors": 0, "error_types": 0, "top_errors": []}
        except Exception as e:
            logger.error(f"错误分析失败: {e}")
            return {"total_errors": 0, "error_types": 0, "top_errors": []}

    def get_top_error_patterns(self, days: int = 7, limit: int = 5) -> List[Dict[str, Any]]:
        """
        获取Top错误模式

        Args:
            days: 分析天数
            limit: 返回数量

        Returns:
            Top错误模式列表
        """
        report = self.analyze_errors(days)
        return report.get("top_errors", [])[:limit]

    def generate_regression_samples(self, days: int = 7) -> List[Dict[str, Any]]:
        """
        从错误聚类生成回归测试样本

        Args:
            days: 分析天数

        Returns:
            回归测试样本列表
        """
        report = self.analyze_errors(days)
        samples = []

        for error in report.get("top_errors", []):
            error_type = error.get("error_type", "Unknown")
            examples = error.get("examples", [])

            for example in examples[:3]:  # 每种错误最多3个样本
                samples.append({
                    "sample_id": f"regression_{error_type}_{len(samples)}",
                    "source": "production_error",
                    "error_type": error_type,
                    "example": example,
                    "category": "error_recovery",
                    "difficulty": "hard"
                })

        return samples


class HarnessWeeklyReportIntegration:
    """
    Harness周度报告集成

    封装对harness/feedback/weekly_report.py的协同。
    """

    def __init__(self, report_dir: str = None, trace_dir: str = None):
        """初始化"""
        self.report_dir = report_dir
        self.trace_dir = trace_dir
        self._initialized = False

    def _ensure_initialized(self):
        """确保已初始化"""
        if self._initialized:
            return
        self._initialized = True

    def generate_combined_report(
        self,
        eval_report: str,
        year: int = None,
        week: int = None
    ) -> str:
        """
        生成组合报告（评估报告 + Harness周度报告）

        Args:
            eval_report: 评估报告内容（Markdown）
            year: 年份
            week: 周数

        Returns:
            组合报告内容
        """
        self._ensure_initialized()

        try:
            from supply_chain_agent.harness.feedback.weekly_report import WeeklyReportGenerator

            generator = WeeklyReportGenerator(
                report_dir=self.report_dir or "/root/Supply-Chain-Agent/harness/improvements",
                trace_dir=self.trace_dir or "/root/autodl-tmp/harness-traces"
            )

            # 生成Harness周度报告
            harness_report_path = generator.generate(year, week)

            # 读取Harness报告
            with open(harness_report_path, 'r', encoding='utf-8') as f:
                harness_report = f.read()

            # 组合报告
            combined = f"""# 综合分析报告

本报告由评估系统和Harness Engineering联合生成。

---

{eval_report}

---

## Harness Engineering报告

{harness_report}
"""
            return combined

        except ImportError as e:
            logger.warning(f"Harness周度报告模块不可用: {e}")
            return eval_report
        except Exception as e:
            logger.error(f"组合报告生成失败: {e}")
            return eval_report


# 全局实例
_rules_integration: Optional[HarnessRulesIntegration] = None
_evals_integration: Optional[HarnessEvalsIntegration] = None
_error_cluster_integration: Optional[HarnessErrorClusterIntegration] = None


def get_rules_integration() -> HarnessRulesIntegration:
    """获取Rules集成实例"""
    global _rules_integration
    if _rules_integration is None:
        _rules_integration = HarnessRulesIntegration()
    return _rules_integration


def get_evals_integration() -> HarnessEvalsIntegration:
    """获取Evals集成实例"""
    global _evals_integration
    if _evals_integration is None:
        _evals_integration = HarnessEvalsIntegration()
    return _evals_integration


def get_error_cluster_integration(
    log_dir: str = None,
    trace_dir: str = None
) -> HarnessErrorClusterIntegration:
    """获取错误聚类集成实例"""
    global _error_cluster_integration
    if _error_cluster_integration is None:
        _error_cluster_integration = HarnessErrorClusterIntegration(log_dir, trace_dir)
    return _error_cluster_integration
