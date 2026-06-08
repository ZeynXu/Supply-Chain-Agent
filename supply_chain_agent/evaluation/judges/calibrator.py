"""
黄金集校准器

使用黄金集校准LLM Judge评分，计算Cohen's Kappa等指标。
"""

import logging
from datetime import datetime
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

from ..core.base import GoldenSample, QualityScore, QualityAnnotations
from .llm_judge import LLMJudge

logger = logging.getLogger(__name__)


@dataclass
class CalibrationResult:
    """校准结果"""
    kappa: float                 # Cohen's Kappa
    precision: float             # 精确率
    recall: float                # 召回率
    f1: float                    # F1分数
    sample_size: int             # 样本数
    dimension_kappas: Dict[str, float] = field(default_factory=dict)  # 各维度Kappa
    calibrated_at: datetime = field(default_factory=datetime.now)
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "kappa": self.kappa,
            "precision": self.precision,
            "recall": self.recall,
            "f1": self.f1,
            "sample_size": self.sample_size,
            "dimension_kappas": self.dimension_kappas,
            "calibrated_at": self.calibrated_at.isoformat(),
            "details": self.details
        }

    def is_acceptable(self, threshold: float = 0.6) -> bool:
        """判断校准结果是否可接受"""
        return self.kappa >= threshold


@dataclass
class AgreementMatrix:
    """一致性矩阵"""
    labels: List[str]
    matrix: List[List[int]]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "labels": self.labels,
            "matrix": self.matrix
        }


class Calibrator:
    """
    黄金集校准器

    使用人工标注的黄金集校准LLM Judge评分。
    """

    # 评分等级标签
    LABELS = ["excellent", "good", "acceptable", "poor"]

    # Kappa阈值
    KAPPA_EXCELLENT = 0.8
    KAPPA_GOOD = 0.6
    KAPFA_ACCEPTABLE = 0.4

    def __init__(
        self,
        judge: LLMJudge,
        golden_samples: Optional[List[GoldenSample]] = None
    ):
        """
        初始化

        Args:
            judge: LLM Judge实例
            golden_samples: 黄金样本列表
        """
        self.judge = judge
        self.golden_samples = golden_samples or []

    def add_sample(self, sample: GoldenSample):
        """添加黄金样本"""
        self.golden_samples.append(sample)

    def load_samples(self, samples: List[GoldenSample]):
        """加载黄金样本"""
        self.golden_samples.extend(samples)

    async def calibrate(self) -> CalibrationResult:
        """
        执行校准

        Returns:
            CalibrationResult: 校准结果
        """
        if not self.golden_samples:
            logger.warning("No golden samples for calibration")
            return CalibrationResult(
                kappa=0.0,
                precision=0.0,
                recall=0.0,
                f1=0.0,
                sample_size=0,
                details={"error": "No samples"}
            )

        # 收集预测和真实标签
        predictions = []
        ground_truth = []

        for sample in self.golden_samples:
            # 获取LLM Judge预测
            try:
                score = await self.judge.score(
                    sample.user_query,
                    sample.gold_result.expected_response
                )
                pred_labels = score.to_labels()
            except Exception as e:
                logger.error(f"Judge failed for sample {sample.sample_id}: {e}")
                continue

            # 获取人工标注
            if sample.gold_result.quality_annotations is None:
                logger.warning(f"No annotations for sample {sample.sample_id}")
                continue

            true_labels = sample.gold_result.quality_annotations.to_labels()

            predictions.append(pred_labels)
            ground_truth.append(true_labels)

        if not predictions:
            return CalibrationResult(
                kappa=0.0,
                precision=0.0,
                recall=0.0,
                f1=0.0,
                sample_size=0,
                details={"error": "No valid predictions"}
            )

        # 计算各维度Kappa
        dimension_kappas = {}
        for dim in ["helpfulness", "clarity", "faithfulness"]:
            pred = [p[dim] for p in predictions]
            true = [t[dim] for t in ground_truth]
            dimension_kappas[dim] = self._calculate_cohen_kappa(pred, true)

        # 计算整体指标（使用帮助性维度作为主要指标）
        main_pred = [p["helpfulness"] for p in predictions]
        main_true = [t["helpfulness"] for t in ground_truth]

        kappa = self._calculate_cohen_kappa(main_pred, main_true)
        precision, recall, f1 = self._calculate_metrics(main_pred, main_true)

        return CalibrationResult(
            kappa=kappa,
            precision=precision,
            recall=recall,
            f1=f1,
            sample_size=len(predictions),
            dimension_kappas=dimension_kappas,
            details={
                "samples_evaluated": len(predictions),
                "samples_total": len(self.golden_samples)
            }
        )

    async def calibrate_dimension(self, dimension: str) -> float:
        """
        校准单个维度

        Args:
            dimension: 维度名称

        Returns:
            Cohen's Kappa值
        """
        predictions = []
        ground_truth = []

        for sample in self.golden_samples:
            if sample.gold_result.quality_annotations is None:
                continue

            try:
                score = await self.judge.score(
                    sample.user_query,
                    sample.gold_result.expected_response
                )
                pred_labels = score.to_labels()
                true_labels = sample.gold_result.quality_annotations.to_labels()

                predictions.append(pred_labels.get(dimension, "acceptable"))
                ground_truth.append(true_labels.get(dimension, "acceptable"))
            except Exception as e:
                logger.error(f"Judge failed: {e}")
                continue

        return self._calculate_cohen_kappa(predictions, ground_truth)

    def _calculate_cohen_kappa(
        self,
        predictions: List[str],
        ground_truth: List[str]
    ) -> float:
        """
        计算Cohen's Kappa

        Kappa = (Po - Pe) / (1 - Pe)
        Po: 观察一致性
        Pe: 期望一致性
        """
        if not predictions or not ground_truth:
            return 0.0

        n = len(predictions)
        labels = list(set(predictions + ground_truth))

        # 构建混淆矩阵
        label_to_idx = {l: i for i, l in enumerate(labels)}
        k = len(labels)
        matrix = [[0] * k for _ in range(k)]

        for pred, true in zip(predictions, ground_truth):
            i = label_to_idx[true]
            j = label_to_idx[pred]
            matrix[i][j] += 1

        # 计算观察一致性 Po
        correct = sum(matrix[i][i] for i in range(k))
        po = correct / n

        # 计算期望一致性 Pe
        row_sums = [sum(matrix[i]) for i in range(k)]
        col_sums = [sum(matrix[i][j] for i in range(k)) for j in range(k)]
        pe = sum(row_sums[i] * col_sums[i] for i in range(k)) / (n * n)

        # 计算Kappa
        if pe == 1.0:
            return 1.0 if po == 1.0 else 0.0

        kappa = (po - pe) / (1 - pe)
        return round(kappa, 4)

    def _calculate_metrics(
        self,
        predictions: List[str],
        ground_truth: List[str]
    ) -> tuple[float, float, float]:
        """
        计算精确率、召回率、F1

        将"excellent"和"good"视为正类
        """
        positive_labels = {"excellent", "good"}

        tp = sum(1 for p, t in zip(predictions, ground_truth)
                 if p in positive_labels and t in positive_labels)
        fp = sum(1 for p, t in zip(predictions, ground_truth)
                 if p in positive_labels and t not in positive_labels)
        fn = sum(1 for p, t in zip(predictions, ground_truth)
                 if p not in positive_labels and t in positive_labels)

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

        return round(precision, 4), round(recall, 4), round(f1, 4)

    def get_calibration_report(self, result: CalibrationResult) -> str:
        """
        生成校准报告

        Args:
            result: 校准结果

        Returns:
            Markdown格式报告
        """
        kappa_status = "✅ 优秀" if result.kappa >= self.KAPPA_EXCELLENT else \
                       "✅ 良好" if result.kappa >= self.KAPPA_GOOD else \
                       "⚠️ 可接受" if result.kappa >= self.KAPFA_ACCEPTABLE else \
                       "❌ 需改进"

        report = f"""# LLM Judge校准报告

**校准时间**: {result.calibrated_at.strftime('%Y-%m-%d %H:%M:%S')}
**样本数量**: {result.sample_size}

---

## 1. 整体评估

| 指标 | 数值 | 状态 |
|------|------|------|
| Cohen's Kappa | {result.kappa:.4f} | {kappa_status} |
| 精确率 | {result.precision:.4f} | - |
| 召回率 | {result.recall:.4f} | - |
| F1分数 | {result.f1:.4f} | - |

---

## 2. 各维度Kappa

| 维度 | Kappa | 状态 |
|------|-------|------|
"""
        for dim, kappa in result.dimension_kappas.items():
            status = "✅" if kappa >= self.KAPPA_GOOD else "⚠️" if kappa >= self.KAPFA_ACCEPTABLE else "❌"
            report += f"| {dim} | {kappa:.4f} | {status} |\n"

        report += f"""
---

## 3. 建议

"""
        if result.kappa >= self.KAPPA_GOOD:
            report += "- LLM Judge评分与人工标注一致性良好，可用于生产环境\n"
        else:
            report += "- 建议优化评分Prompt或调整评分标准\n"
            report += "- 可增加黄金样本以提高校准精度\n"

        return report
