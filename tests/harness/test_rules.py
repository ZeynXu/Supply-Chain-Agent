"""业务规则加载器和评估器测试"""

import pytest
import tempfile
import yaml
from pathlib import Path

from supply_chain_agent.harness.rules.loader import RuleLoader, BusinessRule
from supply_chain_agent.harness.rules.evaluator import (
    RuleEvaluator,
    SafeExpressionEvaluator,
    EvaluationResult,
)


class TestRuleLoader:
    """规则加载器测试"""

    def test_load_rules_from_yaml(self, tmp_path):
        """测试从 YAML 文件加载规则"""
        # 创建临时 YAML 文件
        yaml_content = """
version: "1.0"
metadata:
  description: "测试规则"
rules:
  - id: "test_rule"
    name: "测试规则"
    enabled: true
    severity: "warn"
    condition: "amount > 100"
    action: "notify"
    message: "金额超过100"
"""
        yaml_file = tmp_path / "test_rules.yaml"
        yaml_file.write_text(yaml_content, encoding='utf-8')

        # 加载规则
        loader = RuleLoader(rules_path=str(yaml_file), auto_reload=False)

        # 验证
        assert len(loader._rules) == 1
        rule = loader.get_rule("test_rule")
        assert rule is not None
        assert rule.name == "测试规则"
        assert rule.severity == "warn"
        assert rule.enabled is True

    def test_get_all_rules_returns_enabled_only(self, tmp_path):
        """测试 get_all_rules 只返回启用的规则"""
        yaml_content = """
version: "1.0"
rules:
  - id: "enabled_rule"
    name: "启用规则"
    enabled: true
    severity: "warn"
    condition: "true"
    action: "notify"
    message: "启用"
  - id: "disabled_rule"
    name: "禁用规则"
    enabled: false
    severity: "warn"
    condition: "true"
    action: "notify"
    message: "禁用"
"""
        yaml_file = tmp_path / "test_rules.yaml"
        yaml_file.write_text(yaml_content, encoding='utf-8')

        loader = RuleLoader(rules_path=str(yaml_file), auto_reload=False)
        all_rules = loader.get_all_rules()

        assert len(all_rules) == 1
        assert all_rules[0].id == "enabled_rule"

    def test_reload_rules(self, tmp_path):
        """测试重新加载规则"""
        yaml_content = """
version: "1.0"
rules:
  - id: "rule1"
    name: "规则1"
    enabled: true
    severity: "warn"
    condition: "true"
    action: "notify"
    message: "消息"
"""
        yaml_file = tmp_path / "test_rules.yaml"
        yaml_file.write_text(yaml_content, encoding='utf-8')

        loader = RuleLoader(rules_path=str(yaml_file), auto_reload=False)
        assert len(loader._rules) == 1

        # 修改文件
        new_content = yaml_content + """
  - id: "rule2"
    name: "规则2"
    enabled: true
    severity: "block"
    condition: "false"
    action: "reject"
    message: "新规则"
"""
        yaml_file.write_text(new_content, encoding='utf-8')

        # 重新加载
        result = loader.reload_rules()

        assert result is True
        assert len(loader._rules) == 2

    def test_file_not_found_raises_error(self):
        """测试文件不存在时抛出异常"""
        with pytest.raises(FileNotFoundError):
            RuleLoader(rules_path="/nonexistent/path.yaml", auto_reload=False)


class TestSafeExpressionEvaluator:
    """安全表达式评估器测试"""

    def test_evaluate_simple_comparison(self):
        """测试简单比较表达式"""
        evaluator = SafeExpressionEvaluator()

        result = evaluator.evaluate("amount > 100", {"amount": 150})
        assert result is True

        result = evaluator.evaluate("amount > 100", {"amount": 50})
        assert result is False

    def test_evaluate_dict_get(self):
        """测试字典 get 方法"""
        evaluator = SafeExpressionEvaluator()

        result = evaluator.evaluate("order.get('status') == 'cancelled'",
                                   {"order": {"status": "cancelled"}})
        assert result is True

        result = evaluator.evaluate("order.get('status') == 'cancelled'",
                                   {"order": {"status": "active"}})
        assert result is False

    def test_evaluate_and_or_logic(self):
        """测试逻辑运算"""
        evaluator = SafeExpressionEvaluator()

        result = evaluator.evaluate("amount > 10 and status == 'active'", {"amount": 15, "status": "active"})
        assert result is True

        result = evaluator.evaluate("amount > 10 or amount > 20", {"amount": 25, "status": "active"})
        assert result is True

    def test_evaluate_in_operator(self):
        """测试 in 操作符"""
        evaluator = SafeExpressionEvaluator()

        result = evaluator.evaluate("status in ['active', 'pending']",
                                   {"status": "active"})
        assert result is True

        result = evaluator.evaluate("status in ['active', 'pending']",
                                   {"status": "cancelled"})
        assert result is False

    def test_disallow_unsafe_operations(self):
        """测试拒绝不安全操作"""
        evaluator = SafeExpressionEvaluator()

        # 不允许访问未授权变量 - 返回 False 而不是抛出异常
        result = evaluator.evaluate("__import__('os').system('ls')", {})
        assert result is False  # 安全起见，返回 False 而不是抛出异常


class TestRuleEvaluator:
    """规则评估引擎测试"""

    @pytest.fixture
    def rule_loader(self, tmp_path):
        """创建测试用规则加载器"""
        yaml_content = """
version: "1.0"
rules:
  - id: "high_amount"
    name: "高金额告警"
    enabled: true
    severity: "warn"
    condition: "amount > 100000"
    action: "notify"
    message: "金额超过10万"
  - id: "blocked_status"
    name: "状态阻止"
    enabled: true
    severity: "block"
    condition: "status == 'cancelled'"
    action: "reject"
    message: "状态已取消"
  - id: "disabled_rule"
    name: "禁用规则"
    enabled: false
    severity: "warn"
    condition: "true"
    action: "notify"
    message: "不应触发"
"""
        yaml_file = tmp_path / "test_rules.yaml"
        yaml_file.write_text(yaml_content, encoding='utf-8')
        return RuleLoader(rules_path=str(yaml_file), auto_reload=False)

    def test_evaluate_all_returns_correct_categories(self, rule_loader):
        """测试 evaluate_all 返回正确分类"""
        evaluator = RuleEvaluator(rule_loader)

        context = {
            "amount": 150000,
            "status": "cancelled"
        }

        issues, warnings, notifications = evaluator.evaluate_all(context)

        # 验证分类
        assert len(warnings) == 1  # high_amount
        assert warnings[0].rule_id == "high_amount"

        assert len(issues) == 1  # blocked_status
        assert issues[0].rule_id == "blocked_status"

        assert len(notifications) == 0

    def test_disabled_rule_not_evaluated(self, rule_loader):
        """测试禁用规则不被评估"""
        evaluator = RuleEvaluator(rule_loader)

        context = {"amount": 50000, "status": "active"}
        issues, warnings, notifications = evaluator.evaluate_all(context)

        # disabled_rule 不应触发
        all_results = issues + warnings + notifications
        assert not any(r.rule_id == "disabled_rule" for r in all_results)

    def test_evaluate_single_rule(self, rule_loader):
        """测试评估单个规则"""
        evaluator = RuleEvaluator(rule_loader)

        context = {"amount": 200000, "status": "active"}
        result = evaluator.evaluate_rule("high_amount", context)

        assert result is not None
        assert result.triggered is True
        assert result.severity == "warn"
