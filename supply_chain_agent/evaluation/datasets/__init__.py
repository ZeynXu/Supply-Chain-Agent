"""
评估数据集模块

包含黄金集和回归测试集的管理。
"""

from pathlib import Path
import json
from datetime import datetime
from typing import List, Optional, Dict, Any

# 数据集目录
DATASETS_DIR = Path(__file__).parent
GOLDEN_DIR = DATASETS_DIR / "golden"
REGRESSION_DIR = DATASETS_DIR / "regression"


def load_golden_samples() -> List[Dict[str, Any]]:
    """加载黄金样本"""
    samples = []
    golden_file = GOLDEN_DIR / "samples.json"

    if golden_file.exists():
        with open(golden_file, 'r', encoding='utf-8') as f:
            samples = json.load(f)

    return samples


def load_regression_samples() -> List[Dict[str, Any]]:
    """加载回归测试样本"""
    samples = []
    regression_file = REGRESSION_DIR / "samples.json"

    if regression_file.exists():
        with open(regression_file, 'r', encoding='utf-8') as f:
            samples = json.load(f)

    return samples


def save_golden_samples(samples: List[Dict[str, Any]]):
    """保存黄金样本"""
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    golden_file = GOLDEN_DIR / "samples.json"

    with open(golden_file, 'w', encoding='utf-8') as f:
        json.dump(samples, f, ensure_ascii=False, indent=2)


# 示例黄金样本
EXAMPLE_GOLDEN_SAMPLES = [
    {
        "sample_id": "golden_001",
        "user_query": "查询客户C001的订单信息",
        "gold_result": {
            "expected_intent": {
                "intent_level_1": "信息查询",
                "intent_level_2": "订单查询"
            },
            "expected_tools": ["query_order"],
            "expected_response_keywords": ["订单", "C001"],
            "expected_violations": []
        },
        "category": "intent",
        "difficulty": "easy"
    },
    {
        "sample_id": "golden_002",
        "user_query": "创建一个紧急工单，客户是C002，问题描述是货物损坏",
        "gold_result": {
            "expected_intent": {
                "intent_level_1": "工单管理",
                "intent_level_2": "创建工单"
            },
            "expected_tools": ["create_work_order"],
            "expected_response_keywords": ["工单", "创建成功", "C002"],
            "expected_violations": []
        },
        "category": "tool",
        "difficulty": "medium"
    }
]
