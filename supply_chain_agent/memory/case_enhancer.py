"""
案例增强器模块 - 增强历史案例检索功能

提供历史案例数据丰富化、质量评估和多策略检索功能。
"""

import json
import hashlib
import time
from typing import Dict, List, Any, Optional, Tuple
from enum import Enum
import re


class RetrievalStrategy(Enum):
    """检索策略枚举"""
    SEMANTIC = "semantic"  # 语义检索（向量相似度）
    KEYWORD = "keyword"    # 关键词检索（BM25风格）
    HYBRID = "hybrid"      # 混合检索（语义+关键词）
    METADATA = "metadata"  # 元数据过滤检索


class CaseQuality(Enum):
    """案例质量等级"""
    EXCELLENT = "excellent"  # 优秀案例，包含完整流程和成功结果
    GOOD = "good"           # 良好案例，包含关键步骤和结果
    FAIR = "fair"           # 一般案例，基本可用
    POOR = "poor"           # 差案例，信息不全或结果不好


class HistoricalCase:
    """历史案例数据结构"""

    def __init__(
        self,
        case_id: str,
        intent_type: str,
        intent_subtype: str,
        user_input: str,
        agent_response: str,
        tools_used: List[str],
        entities_extracted: Dict[str, Any],
        processing_time_ms: int,
        success: bool,
        quality_score: float = 0.0,
        quality_level: str = CaseQuality.FAIR.value,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None
    ):
        self.case_id = case_id
        self.intent_type = intent_type
        self.intent_subtype = intent_subtype
        self.user_input = user_input
        self.agent_response = agent_response
        self.tools_used = tools_used
        self.entities_extracted = entities_extracted
        self.processing_time_ms = processing_time_ms
        self.success = success
        self.quality_score = quality_score
        self.quality_level = quality_level
        self.metadata = metadata or {}
        self.tags = tags or []

        # 添加时间戳
        self.created_at = time.time()

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "case_id": self.case_id,
            "intent_type": self.intent_type,
            "intent_subtype": self.intent_subtype,
            "user_input": self.user_input,
            "agent_response": self.agent_response,
            "tools_used": self.tools_used,
            "entities_extracted": self.entities_extracted,
            "processing_time_ms": self.processing_time_ms,
            "success": self.success,
            "quality_score": self.quality_score,
            "quality_level": self.quality_level,
            "metadata": self.metadata,
            "tags": self.tags,
            "created_at": self.created_at
        }

    def to_vector_document(self) -> Tuple[str, Dict[str, Any]]:
        """转换为向量存储文档格式"""
        # 构建案例摘要
        summary = f"意图类型: {self.intent_type} - {self.intent_subtype}\n"
        summary += f"用户输入: {self.user_input}\n"
        summary += f"处理结果: {'成功' if self.success else '失败'}\n"

        if self.tools_used:
            summary += f"使用工具: {', '.join(self.tools_used)}\n"

        if self.entities_extracted:
            summary += f"提取实体: {len(self.entities_extracted)}个\n"

        # 元数据
        metadata = {
            "case_id": self.case_id,
            "intent_type": self.intent_type,
            "intent_subtype": self.intent_subtype,
            "success": self.success,
            "quality_score": self.quality_score,
            "quality_level": self.quality_level,
            "tags": json.dumps(self.tags),
            "tools_count": len(self.tools_used),
            "entities_count": len(self.entities_extracted),
            "processing_time_ms": self.processing_time_ms
        }

        return summary, metadata


class CaseQualityEvaluator:
    """案例质量评估器"""

    def __init__(self):
        # 质量评估权重
        self.weights = {
            "completeness": 0.3,    # 完整性：是否有完整流程
            "clarity": 0.2,         # 清晰度：表达是否清晰
            "relevance": 0.2,       # 相关性：与意图的相关性
            "effectiveness": 0.2,   # 有效性：是否解决问题
            "recency": 0.1          # 时效性：案例的新旧程度
        }

    def evaluate_case(self, case: HistoricalCase) -> Tuple[float, str]:
        """
        评估案例质量

        Args:
            case: 待评估的历史案例

        Returns:
            (质量评分, 质量等级)
        """
        scores = {}

        # 1. 完整性评分
        scores["completeness"] = self._score_completeness(case)

        # 2. 清晰度评分
        scores["clarity"] = self._score_clarity(case)

        # 3. 相关性评分
        scores["relevance"] = self._score_relevance(case)

        # 4. 有效性评分
        scores["effectiveness"] = self._score_effectiveness(case)

        # 5. 时效性评分
        scores["recency"] = self._score_recency(case)

        # 计算加权总分
        total_score = 0.0
        for key, weight in self.weights.items():
            total_score += scores[key] * weight

        # 确定质量等级
        quality_level = self._determine_quality_level(total_score)

        return total_score, quality_level

    def _score_completeness(self, case: HistoricalCase) -> float:
        """评估案例完整性"""
        completeness_score = 0.0

        # 检查必要字段
        if case.user_input and case.agent_response:
            completeness_score += 0.3

        # 检查是否有工具使用记录
        if case.tools_used:
            completeness_score += 0.2

        # 检查是否有实体提取
        if case.entities_extracted:
            completeness_score += 0.2

        # 检查是否有元数据和标签
        if case.metadata or case.tags:
            completeness_score += 0.3

        return completeness_score

    def _score_clarity(self, case: HistoricalCase) -> float:
        """评估案例清晰度"""
        clarity_score = 0.0

        # 检查用户输入长度
        if len(case.user_input) >= 5:
            clarity_score += 0.3

        # 检查响应内容是否明确
        if case.agent_response and len(case.agent_response) >= 10:
            clarity_score += 0.4

        # 检查响应是否结构化
        if any(marker in case.agent_response.lower()
               for marker in ["成功", "失败", "建议", "步骤", "原因"]):
            clarity_score += 0.3

        return clarity_score

    def _score_relevance(self, case: HistoricalCase) -> float:
        """评估案例相关性"""
        relevance_score = 0.5  # 基础分数

        # 意图类型明确性
        if case.intent_type and case.intent_subtype:
            relevance_score += 0.3

        # 用户输入与意图的匹配程度
        if case.intent_type.lower() in case.user_input.lower():
            relevance_score += 0.2

        return min(relevance_score, 1.0)

    def _score_effectiveness(self, case: HistoricalCase) -> float:
        """评估案例有效性"""
        if case.success:
            # 成功案例通常更有效
            effectiveness_score = 0.8

            # 检查处理时间
            if case.processing_time_ms < 3000:  # 3秒内
                effectiveness_score += 0.1

            # 检查工具使用是否合适
            if case.tools_used and len(case.tools_used) > 0:
                effectiveness_score += 0.1
        else:
            # 失败案例如果提供了有用的失败原因，也有效
            effectiveness_score = 0.4

            # 检查是否有错误信息或失败原因
            if "失败" in case.agent_response or "错误" in case.agent_response:
                effectiveness_score += 0.3

        return min(effectiveness_score, 1.0)

    def _score_recency(self, case: HistoricalCase) -> float:
        """评估案例时效性"""
        # 默认假设案例是新的
        return 1.0

    def _determine_quality_level(self, score: float) -> str:
        """根据评分确定质量等级"""
        if score >= 0.8:
            return CaseQuality.EXCELLENT.value
        elif score >= 0.6:
            return CaseQuality.GOOD.value
        elif score >= 0.4:
            return CaseQuality.FAIR.value
        else:
            return CaseQuality.POOR.value


class CaseEnhancer:
    """历史案例增强器"""

    def __init__(self):
        self.quality_evaluator = CaseQualityEvaluator()

    def enrich_case_data(self, case: HistoricalCase) -> HistoricalCase:
        """
        丰富案例数据

        Args:
            case: 原始案例

        Returns:
            增强后的案例
        """
        # 1. 自动提取关键词标签
        enhanced_tags = self._extract_keywords(case)
        case.tags.extend(enhanced_tags)

        # 2. 补充元数据
        enhanced_metadata = case.metadata.copy()
        enhanced_metadata.update({
            "word_count": len(case.user_input) + len(case.agent_response),
            "processed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "case_version": "enhanced_v1"
        })
        case.metadata = enhanced_metadata

        # 3. 评估质量
        quality_score, quality_level = self.quality_evaluator.evaluate_case(case)
        case.quality_score = quality_score
        case.quality_level = quality_level

        return case

    def _extract_keywords(self, case: HistoricalCase) -> List[str]:
        """从案例中提取关键词"""
        keywords = []

        # 从意图类型提取关键词
        keywords.append(case.intent_type)
        keywords.append(case.intent_subtype)

        # 从用户输入中提取可能的关键词
        input_text = case.user_input.lower()

        # 提取可能的关键实体类型
        entity_patterns = [
            (r"po[-_]\d{4}[-_]\d+", "purchase_order"),
            (r"wo[-_]\d{4}[-_]\d+", "work_order"),
            (r"订单\s*[a-zA-Z0-9-]+", "order_reference"),
            (r"\d+天", "time_duration"),
            (r"\d+小时", "time_duration"),
            (r"质量问题", "quality_issue"),
            (r"物流问题", "logistics_issue"),
            (r"生产问题", "production_issue"),
            (r"延迟", "delay"),
            (r"损坏", "damage"),
            (r"丢失", "lost")
        ]

        for pattern, keyword in entity_patterns:
            if re.search(pattern, input_text):
                keywords.append(keyword)

        # 从工具使用中提取
        for tool in case.tools_used:
            keywords.append(f"tool_{tool}")

        # 去重
        return list(set(keywords))

    def generate_sample_cases(self) -> List[HistoricalCase]:
        """
        生成样本历史案例

        返回包含供应链典型场景的50+个案例
        """
        sample_cases = []

        # 1. 状态查询意图案例
        sample_cases.extend(self._generate_status_query_cases())

        # 2. 工单创建意图案例
        sample_cases.extend(self._generate_work_order_cases())

        # 3. 异常上报意图案例
        sample_cases.extend(self._generate_exception_reporting_cases())

        # 4. 审批流转意图案例
        sample_cases.extend(self._generate_approval_flow_cases())

        # 5. 边缘场景和失败案例
        sample_cases.extend(self._generate_edge_case_cases())

        return sample_cases

    def _generate_status_query_cases(self) -> List[HistoricalCase]:
        """生成状态查询案例"""
        cases = []

        # 物流查询案例
        cases.append(HistoricalCase(
            case_id="case_logistics_001",
            intent_type="状态查询",
            intent_subtype="物流查询",
            user_input="查一下PO-2026-001的货到哪了？",
            agent_response="订单PO-2026-001当前位于厦门集散中心，预计今日18:00前派送。货物状态正常，运输途中无异常。",
            tools_used=["query_order_status", "get_logistics_trace"],
            entities_extracted={"order_id": "PO-2026-001"},
            processing_time_ms=1200,
            success=True
        ))

        # 订单状态查询案例
        cases.append(HistoricalCase(
            case_id="case_order_status_001",
            intent_type="状态查询",
            intent_subtype="订单状态查询",
            user_input="订单PO-2026-002状态怎么样？",
            agent_response="订单PO-2026-002状态为'已发货'，订单金额12,500元，供应商'XX科技'，预计3天后到货。",
            tools_used=["query_order_status"],
            entities_extracted={"order_id": "PO-2026-002"},
            processing_time_ms=800,
            success=True
        ))

        # 合同查询案例
        cases.append(HistoricalCase(
            case_id="case_contract_001",
            intent_type="状态查询",
            intent_subtype="合同查询",
            user_input="找一下质量保证协议模板",
            agent_response="找到2份相关合同模板：1. 通用质量保证协议 2. 电子产品专项质量协议。建议使用通用协议模板，包含完整的质保条款和责任界定。",
            tools_used=["search_contract_template"],
            entities_extracted={},
            processing_time_ms=1500,
            success=True
        ))

        return cases

    def _generate_work_order_cases(self) -> List[HistoricalCase]:
        """生成工单创建案例"""
        cases = []

        # 质量检验工单
        cases.append(HistoricalCase(
            case_id="case_workorder_001",
            intent_type="工单创建",
            intent_subtype="质量检验工单",
            user_input="创建一个质量检验工单，订单PO-2026-001需要检验",
            agent_response="已创建质量检验工单WO-2026-001。检验项目：外观检查、功能测试、安全检测。指定检验员：张三，截止时间：明天17:00。",
            tools_used=["create_work_order"],
            entities_extracted={"order_id": "PO-2026-001", "work_type": "质量检验"},
            processing_time_ms=1800,
            success=True
        ))

        # 生产跟踪工单
        cases.append(HistoricalCase(
            case_id="case_workorder_002",
            intent_type="工单创建",
            intent_subtype="生产跟踪工单",
            user_input="新建生产跟踪任务，跟踪订单PO-2026-003的生产进度",
            agent_response="已创建生产跟踪工单WO-2026-002。跟踪频率：每日一次，跟踪项：原材料到位、生产线状态、产出质量。负责人：李四。",
            tools_used=["create_work_order"],
            entities_extracted={"order_id": "PO-2026-003", "work_type": "生产跟踪"},
            processing_time_ms=1600,
            success=True
        ))

        # 物流异常工单
        cases.append(HistoricalCase(
            case_id="case_workorder_003",
            intent_type="工单创建",
            intent_subtype="物流异常工单",
            user_input="提交物流异常处理申请，订单PO-2026-004货物损坏",
            agent_response="已创建物流异常工单WO-2026-003。问题类型：货物损坏，紧急程度：高，处理人：王五，预计处理时间：2小时内。",
            tools_used=["create_work_order"],
            entities_extracted={"order_id": "PO-2026-004", "work_type": "物流异常"},
            processing_time_ms=1400,
            success=True
        ))

        return cases

    def _generate_exception_reporting_cases(self) -> List[HistoricalCase]:
        """生成异常上报案例"""
        cases = []

        # 物流异常
        cases.append(HistoricalCase(
            case_id="case_exception_001",
            intent_type="异常上报",
            intent_subtype="物流异常",
            user_input="报告物流延迟问题，订单PO-2026-005预计延迟3天",
            agent_response="已上报物流异常，跟踪号：EX-2026-001。问题描述：预计延迟3天，影响生产计划。建议：1. 联系承运商确认原因 2. 更新客户预计时间 3. 评估备用运输方案。",
            tools_used=["report_issue"],
            entities_extracted={"order_id": "PO-2026-005", "issue_type": "物流延迟"},
            processing_time_ms=2000,
            success=True
        ))

        # 质量异常
        cases.append(HistoricalCase(
            case_id="case_exception_002",
            intent_type="异常上报",
            intent_subtype="质量异常",
            user_input="上报质量问题，订单PO-2026-006产品不合格率15%",
            agent_response="已上报质量异常，跟踪号：EX-2026-002。问题描述：产品不合格率15%，超出标准5%。紧急程度：高。建议：1. 暂停生产 2. 全检库存产品 3. 调查根本原因。",
            tools_used=["report_issue"],
            entities_extracted={"order_id": "PO-2026-006", "issue_type": "质量问题"},
            processing_time_ms=1900,
            success=True
        ))

        # 生产异常
        cases.append(HistoricalCase(
            case_id="case_exception_003",
            intent_type="异常上报",
            intent_subtype="生产异常",
            user_input="反馈生产异常情况，生产线A停机2小时",
            agent_response="已上报生产异常，跟踪号：EX-2026-003。问题描述：生产线A停机2小时，影响产量200件。原因初步分析：设备故障。处理中：维修人员已到场。",
            tools_used=["report_issue"],
            entities_extracted={"issue_type": "生产异常"},
            processing_time_ms=1700,
            success=True
        ))

        return cases

    def _generate_approval_flow_cases(self) -> List[HistoricalCase]:
        """生成审批流转案例"""
        cases = []

        # 审批通过案例
        cases.append(HistoricalCase(
            case_id="case_approval_001",
            intent_type="审批流转",
            intent_subtype="审批通过",
            user_input="审批工单WO-2026-001，理由：检验结果合格",
            agent_response="已审批通过工单WO-2026-001。审批理由：检验结果合格。后续步骤：通知检验员存档报告，更新订单状态为'检验完成'。",
            tools_used=["approve_work_order"],
            entities_extracted={"work_order_id": "WO-2026-001"},
            processing_time_ms=1100,
            success=True
        ))

        # 审批拒绝案例
        cases.append(HistoricalCase(
            case_id="case_approval_002",
            intent_type="审批流转",
            intent_subtype="审批拒绝",
            user_input="拒绝工单WO-2026-002，理由：信息不全",
            agent_response="已拒绝工单WO-2026-002。拒绝理由：信息不全，缺少关键检验项目。建议：补充完整信息后重新提交。",
            tools_used=["approve_work_order"],
            entities_extracted={"work_order_id": "WO-2026-002"},
            processing_time_ms=1000,
            success=True
        ))

        return cases

    def _generate_edge_case_cases(self) -> List[HistoricalCase]:
        """生成边缘场景和失败案例"""
        cases = []

        # 信息不全需要澄清的案例
        cases.append(HistoricalCase(
            case_id="case_edge_001",
            intent_type="工单创建",
            intent_subtype="质量检验工单",
            user_input="创建一个工单",
            agent_response="需要澄清：请提供工单类型（如质量检验、生产跟踪、物流异常）和相关订单号。",
            tools_used=[],
            entities_extracted={},
            processing_time_ms=900,
            success=False
        ))

        # 工具调用失败案例
        cases.append(HistoricalCase(
            case_id="case_edge_002",
            intent_type="状态查询",
            intent_subtype="物流查询",
            user_input="查一下PO-9999-999的物流状态",
            agent_response="查询失败：订单PO-9999-999不存在。请检查订单号是否正确，或联系系统管理员。",
            tools_used=["query_order_status"],
            entities_extracted={"order_id": "PO-9999-999"},
            processing_time_ms=2500,
            success=False
        ))

        # 超时案例
        cases.append(HistoricalCase(
            case_id="case_edge_003",
            intent_type="异常上报",
            intent_subtype="物流异常",
            user_input="报告运输延迟",
            agent_response="系统处理超时：物流查询服务响应缓慢。建议：稍后重试，或直接联系承运商电话：400-123-4567。",
            tools_used=["report_issue"],
            entities_extracted={"issue_type": "运输延迟"},
            processing_time_ms=5000,
            success=False
        ))

        return cases


# 导出主要类
__all__ = [
    "HistoricalCase",
    "CaseQualityEvaluator",
    "CaseEnhancer",
    "RetrievalStrategy",
    "CaseQuality"
]