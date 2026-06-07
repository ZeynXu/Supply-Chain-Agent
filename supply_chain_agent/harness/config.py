"""
Harness 配置管理

通过环境变量控制各特性的开关。
"""

import os
from dataclasses import dataclass
from typing import Optional
from functools import lru_cache


@dataclass
class HarnessConfig:
    """Harness 配置"""

    # Layer 1: 配置化约束
    rules_enabled: bool = True
    rules_path: Optional[str] = None

    # Layer 2: 可观测性
    structured_logs_enabled: bool = True
    metrics_enabled: bool = True
    trace_enabled: bool = True
    trace_sample_rate: float = 0.01
    trace_dir: str = "/root/autodl-tmp/harness-traces"

    # Layer 2: Evals
    evals_level: int = 1  # 0=禁用, 1=门禁, 2=告警

    # 可选功能
    pre_check_enabled: bool = False

    @classmethod
    def from_env(cls) -> 'HarnessConfig':
        """从环境变量加载配置"""
        return cls(
            rules_enabled=os.getenv("HARNESS_RULES_ENABLED", "true").lower() == "true",
            rules_path=os.getenv("HARNESS_RULES_PATH"),
            structured_logs_enabled=os.getenv("HARNESS_STRUCTURED_LOGS", "true").lower() == "true",
            metrics_enabled=os.getenv("HARNESS_METRICS_ENABLED", "true").lower() == "true",
            trace_enabled=os.getenv("HARNESS_TRACE_ENABLED", "true").lower() == "true",
            trace_sample_rate=float(os.getenv("HARNESS_TRACE_SAMPLE_RATE", "0.01")),
            trace_dir=os.getenv("HARNESS_TRACE_DIR", "/root/autodl-tmp/harness-traces"),
            evals_level=int(os.getenv("HARNESS_EVALS_LEVEL", "1")),
            pre_check_enabled=os.getenv("HARNESS_PRE_CHECK", "false").lower() == "true",
        )


@lru_cache(maxsize=1)
def get_harness_config() -> HarnessConfig:
    """获取 Harness 配置（单例）"""
    return HarnessConfig.from_env()
