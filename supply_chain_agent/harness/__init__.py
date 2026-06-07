"""
Harness Engineering 模块

为 Supply-Chain-Agent 提供工程化能力：
- Layer 1: 配置化约束（业务规则 YAML）
- Layer 2: 验证与可观测（Metrics, Logs, Trace, Evals）
- Layer 3: 反馈与持续改进（错误聚类，周度报告）
"""

from .config import HarnessConfig, get_harness_config

__all__ = [
    "HarnessConfig",
    "get_harness_config",
]
