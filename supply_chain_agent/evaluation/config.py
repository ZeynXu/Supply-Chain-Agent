"""
评估系统配置

定义评估权重、阈值、LLM Judge配置等。
支持YAML配置文件和环境变量覆盖。
"""

import os
import yaml
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, Optional


@dataclass
class LLMJudgeConfig:
    """LLM Judge配置"""
    provider: str = "zhipu"
    model: str = "glm-4-flash"
    temperature: float = 0.1
    max_tokens: int = 1024
    timeout_seconds: int = 30
    api_key: Optional[str] = None  # 从环境变量读取
    base_url: Optional[str] = None  # 自定义API端点

    def __post_init__(self):
        """初始化后处理"""
        # 从环境变量获取API Key
        if self.api_key is None:
            if self.provider == "zhipu":
                self.api_key = os.getenv("ZHIPUAI_API_KEY") or os.getenv("ZHIPU_API_KEY")
            elif self.provider == "openai":
                self.api_key = os.getenv("OPENAI_API_KEY")
            elif self.provider == "anthropic":
                self.api_key = os.getenv("ANTHROPIC_API_KEY")

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（不包含敏感信息）"""
        return {
            "provider": self.provider,
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "timeout_seconds": self.timeout_seconds,
            "base_url": self.base_url
        }


@dataclass
class ThresholdConfig:
    """阈值配置"""
    trajectory_pass: float = 0.75          # 轨迹评分通过阈值
    quality_pass: float = 3.5              # 质量评分通过阈值（5分制）
    intent_accuracy: float = 0.85          # 意图准确率阈值
    tool_accuracy: float = 0.90             # 工具准确率阈值
    latency_p99_ms: float = 5000           # P99延迟阈值（毫秒）
    success_rate: float = 0.75              # 成功率阈值

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "trajectory_pass": self.trajectory_pass,
            "quality_pass": self.quality_pass,
            "intent_accuracy": self.intent_accuracy,
            "tool_accuracy": self.tool_accuracy,
            "latency_p99_ms": self.latency_p99_ms,
            "success_rate": self.success_rate
        }


@dataclass
class TrajectoryWeights:
    """轨迹评分九维权重"""
    tool_selection: float = 0.15           # 工具选择正确性
    params_complete: float = 0.10          # 参数完整性
    params_valid: float = 0.10             # 参数有效性
    execution_order: float = 0.10          # 执行顺序合理性
    audit_compliance: float = 0.15         # 审计规则遵循
    answer_reachability: float = 0.15      # 最终答案可达性
    error_recovery: float = 0.10           # 错误恢复能力
    clarification_efficiency: float = 0.05  # 澄清循环效率
    latency: float = 0.10                  # 响应时间合规性

    def __post_init__(self):
        """验证权重总和为1"""
        total = (
            self.tool_selection +
            self.params_complete +
            self.params_valid +
            self.execution_order +
            self.audit_compliance +
            self.answer_reachability +
            self.error_recovery +
            self.clarification_efficiency +
            self.latency
        )
        if abs(total - 1.0) > 0.001:
            raise ValueError(f"权重总和必须为1.0，当前为 {total}")

    def to_dict(self) -> Dict[str, float]:
        """转换为字典"""
        return {
            "tool_selection": self.tool_selection,
            "params_complete": self.params_complete,
            "params_valid": self.params_valid,
            "execution_order": self.execution_order,
            "audit_compliance": self.audit_compliance,
            "answer_reachability": self.answer_reachability,
            "error_recovery": self.error_recovery,
            "clarification_efficiency": self.clarification_efficiency,
            "latency": self.latency
        }

    @classmethod
    def from_dict(cls, data: Dict[str, float]) -> 'TrajectoryWeights':
        """从字典创建"""
        return cls(**data)


@dataclass
class MonitoringConfig:
    """监控配置"""
    sample_rate: float = 0.05               # 生产采样率 5%
    alert_success_rate: float = 0.75        # 成功率告警阈值
    alert_avg_latency_ms: float = 5000      # 平均延迟告警阈值
    alert_p99_latency_ms: float = 10000     # P99延迟告警阈值
    retention_days: int = 30                # 数据保留天数

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "sample_rate": self.sample_rate,
            "alert_success_rate": self.alert_success_rate,
            "alert_avg_latency_ms": self.alert_avg_latency_ms,
            "alert_p99_latency_ms": self.alert_p99_latency_ms,
            "retention_days": self.retention_days
        }


@dataclass
class EvalConfig:
    """评估系统配置"""
    trajectory_weights: TrajectoryWeights = field(default_factory=TrajectoryWeights)
    thresholds: ThresholdConfig = field(default_factory=ThresholdConfig)
    llm_judge: LLMJudgeConfig = field(default_factory=LLMJudgeConfig)
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)
    enabled: bool = True                    # 评估系统是否启用
    log_level: str = "INFO"                 # 日志级别

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "trajectory_weights": self.trajectory_weights.to_dict(),
            "thresholds": self.thresholds.to_dict(),
            "llm_judge": self.llm_judge.to_dict(),
            "monitoring": self.monitoring.to_dict(),
            "enabled": self.enabled,
            "log_level": self.log_level
        }

    @classmethod
    def from_yaml(cls, path: str) -> 'EvalConfig':
        """从YAML文件加载配置"""
        path = Path(path)
        if not path.exists():
            return cls.get_default()

        with open(path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        return cls._from_dict(data)

    @classmethod
    def _from_dict(cls, data: Dict[str, Any]) -> 'EvalConfig':
        """从字典创建"""
        return cls(
            trajectory_weights=TrajectoryWeights.from_dict(
                data.get("trajectory_weights", {})
            ),
            thresholds=ThresholdConfig(**data.get("thresholds", {})),
            llm_judge=LLMJudgeConfig(**data.get("llm_judge", {})),
            monitoring=MonitoringConfig(**data.get("monitoring", {})),
            enabled=data.get("enabled", True),
            log_level=data.get("log_level", "INFO")
        )

    @classmethod
    def get_default(cls) -> 'EvalConfig':
        """获取默认配置"""
        return cls()

    def save_yaml(self, path: str):
        """保存配置到YAML文件"""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, 'w', encoding='utf-8') as f:
            yaml.dump(self.to_dict(), f, allow_unicode=True, default_flow_style=False)


# 全局配置实例
_eval_config: Optional[EvalConfig] = None


def get_eval_config(config_path: Optional[str] = None) -> EvalConfig:
    """
    获取评估配置

    优先级：
    1. 指定配置文件路径
    2. 环境变量 EVAL_CONFIG_PATH
    3. 默认配置

    Returns:
        EvalConfig: 评估配置实例
    """
    global _eval_config

    if _eval_config is not None:
        return _eval_config

    # 尝试从环境变量获取配置路径
    if config_path is None:
        config_path = os.getenv("EVAL_CONFIG_PATH")

    if config_path:
        _eval_config = EvalConfig.from_yaml(config_path)
    else:
        # 尝试默认路径
        default_path = Path(__file__).parent.parent.parent / "config" / "eval_config.yaml"
        if default_path.exists():
            _eval_config = EvalConfig.from_yaml(str(default_path))
        else:
            _eval_config = EvalConfig.get_default()

    return _eval_config


def reset_eval_config():
    """重置全局配置（用于测试）"""
    global _eval_config
    _eval_config = None


# 创建默认配置文件的默认路径
DEFAULT_CONFIG_YAML = """
# Agent评估系统配置

# 九维轨迹评分权重
trajectory_weights:
  tool_selection: 0.15           # 工具选择正确性
  params_complete: 0.10          # 参数完整性
  params_valid: 0.10             # 参数有效性
  execution_order: 0.10          # 执行顺序合理性
  audit_compliance: 0.15         # 审计规则遵循
  answer_reachability: 0.15      # 最终答案可达性
  error_recovery: 0.10           # 错误恢复能力
  clarification_efficiency: 0.05  # 澄清循环效率
  latency: 0.10                  # 响应时间合规性

# 阈值配置
thresholds:
  trajectory_pass: 0.75           # 轨迹评分通过阈值
  quality_pass: 3.5              # 质量评分通过阈值（5分制）
  intent_accuracy: 0.85          # 意图准确率阈值
  tool_accuracy: 0.90             # 工具准确率阈值
  latency_p99_ms: 5000           # P99延迟阈值（毫秒）
  success_rate: 0.75              # 成功率阈值

# LLM Judge配置
llm_judge:
  provider: "zhipu"
  model: "glm-4-flash"
  temperature: 0.1
  max_tokens: 1024
  timeout_seconds: 30

# 监控配置
monitoring:
  sample_rate: 0.05               # 生产采样率 5%
  alert_success_rate: 0.75        # 成功率告警阈值
  alert_avg_latency_ms: 5000      # 平均延迟告警阈值
  alert_p99_latency_ms: 10000     # P99延迟告警阈值
  retention_days: 30               # 数据保留天数

# 其他配置
enabled: true
log_level: "INFO"
"""
