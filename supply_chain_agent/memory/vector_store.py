"""
Memory System for Supply Chain Agent.

Implements three-layer memory system:
1. Short-term memory: Sliding window with summarization
2. Working memory: LangGraph shared state
3. Long-term memory: Vector store + SQLite for RAG
"""

import sqlite3
import json
import time
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import hashlib
import re
import chromadb
from chromadb.config import Settings

from supply_chain_agent.config import settings

# 导入案例增强器
try:
    from supply_chain_agent.memory.case_enhancer import (
        HistoricalCase,
        CaseQualityEvaluator,
        CaseEnhancer,
        RetrievalStrategy,
        CaseQuality
    )
    CASE_ENHANCER_AVAILABLE = True
except ImportError:
    CASE_ENHANCER_AVAILABLE = False
    # 创建虚拟类用于兼容
    class RetrievalStrategy:
        SEMANTIC = "semantic"
        KEYWORD = "keyword"
        HYBRID = "hybrid"
        METADATA = "metadata"


@dataclass
class MemoryItem:
    """Base memory item."""
    id: str
    content: Dict[str, Any]
    timestamp: float
    memory_type: str  # short_term, working, long_term
    tags: List[str]
    importance: float  # 0.0 to 1.0


class ShortTermMemory:
    """
    Short-term memory with sliding window and summarization.

    Stores recent conversations and operations.
    """

    def __init__(self, window_size: int = 20):
        self.window_size = window_size
        self.memory_window: List[MemoryItem] = []
        self.summary_cache: Optional[str] = None
        self.last_summary_time: float = 0

    def add(self, content: Dict[str, Any], tags: List[str] = None,
            importance: float = 0.5) -> str:
        """
        Add item to short-term memory.

        Args:
            content: Memory content
            tags: Optional tags
            importance: Importance score (0.0-1.0)

        Returns:
            Memory item ID
        """
        item_id = self._generate_id(content)

        item = MemoryItem(
            id=item_id,
            content=content,
            timestamp=time.time(),
            memory_type="short_term",
            tags=tags or [],
            importance=importance
        )

        # Add to window
        self.memory_window.append(item)

        # Maintain window size
        if len(self.memory_window) > self.window_size:
            self.memory_window = self.memory_window[-self.window_size:]

        # Invalidate summary cache
        self.summary_cache = None

        return item_id

    def get_recent(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent memory items.

        Args:
            limit: Number of items to return

        Returns:
            List of recent memory items
        """
        recent = self.memory_window[-limit:]
        return [asdict(item) for item in recent]

    def get_summary(self, force_refresh: bool = False) -> str:
        """
        Get summary of recent memory.

        Args:
            force_refresh: Force summary regeneration

        Returns:
            Text summary
        """
        current_time = time.time()

        if (self.summary_cache is None or force_refresh or
            current_time - self.last_summary_time > 300):  # 5 minutes

            if not self.memory_window:
                self.summary_cache = "无近期记忆"
            else:
                self.summary_cache = self._generate_summary()

            self.last_summary_time = current_time

        return self.summary_cache

    def _generate_summary(self) -> str:
        """Generate summary of memory window."""
        if not self.memory_window:
            return "无近期记忆"

        # Group by agent/action
        groups = {}
        for item in self.memory_window[-10:]:  # Last 10 items
            content = item.content
            agent = content.get("agent", "unknown")
            action = content.get("action", "unknown")

            key = f"{agent}:{action}"
            if key not in groups:
                groups[key] = []
            groups[key].append(item)

        # Build summary
        summary_parts = ["近期活动摘要:"]

        for key, items in groups.items():
            agent, action = key.split(":", 1)
            summary_parts.append(f"- {agent} 执行了 {len(items)} 次 {action}")

        # Add timestamps
        if self.memory_window:
            first_time = datetime.fromtimestamp(self.memory_window[0].timestamp)
            last_time = datetime.fromtimestamp(self.memory_window[-1].timestamp)
            summary_parts.append(f"时间范围: {first_time.strftime('%H:%M')} - {last_time.strftime('%H:%M')}")

        return "\n".join(summary_parts)

    def _generate_id(self, content: Dict[str, Any]) -> str:
        """Generate unique ID for memory item."""
        content_str = json.dumps(content, sort_keys=True)
        timestamp_str = str(time.time())
        combined = content_str + timestamp_str

        return hashlib.md5(combined.encode()).hexdigest()[:12]

    def clear(self):
        """Clear short-term memory."""
        self.memory_window = []
        self.summary_cache = None
        self.last_summary_time = 0


class LongTermMemory:
    """
    Long-term memory with vector store and SQLite.

    Stores SOP manuals, FAQs, and historical cases.
    """

    def __init__(self, vector_store_path: str = "./data/vector_store",
                 sqlite_db_path: str = "./data/agent_memory.db"):
        self.vector_store_path = vector_store_path
        self.sqlite_db_path = sqlite_db_path

        # Initialize vector store
        self.chroma_client = chromadb.PersistentClient(
            path=vector_store_path,
            settings=Settings(anonymized_telemetry=False)
        )

        # Initialize collections
        self.sop_collection = self.chroma_client.get_or_create_collection(
            name="sop_manual",
            metadata={"description": "Standard Operating Procedures"}
        )

        self.faq_collection = self.chroma_client.get_or_create_collection(
            name="faq",
            metadata={"description": "Frequently Asked Questions"}
        )

        self.case_collection = self.chroma_client.get_or_create_collection(
            name="historical_cases",
            metadata={"description": "Historical case records"}
        )

        # Initialize case enhancer if available
        if CASE_ENHANCER_AVAILABLE:
            self.case_enhancer = CaseEnhancer()
            self.quality_evaluator = CaseQualityEvaluator()
        else:
            self.case_enhancer = None
            self.quality_evaluator = None

        # Initialize SQLite database
        self._init_sqlite()

    def _init_sqlite(self):
        """Initialize SQLite database."""
        conn = sqlite3.connect(self.sqlite_db_path)
        cursor = conn.cursor()

        # Create tables
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS work_order_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT NOT NULL,
                intent_type TEXT NOT NULL,
                intent_subtype TEXT,
                entities TEXT,
                tool_results TEXT,
                audit_results TEXT,
                final_report TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                success BOOLEAN,
                error_message TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS memory_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                memory_type TEXT NOT NULL,
                content TEXT NOT NULL,
                embedding_id TEXT,
                tags TEXT,
                importance REAL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                accessed_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tool_usage_stats (
                tool_name TEXT PRIMARY KEY,
                success_count INTEGER DEFAULT 0,
                failure_count INTEGER DEFAULT 0,
                total_time_ms INTEGER DEFAULT 0,
                last_used DATETIME
            )
        """)

        conn.commit()
        conn.close()

    def store_work_order_record(self, order_id: str, intent: Dict[str, Any],
                               tool_results: Dict[str, Any],
                               audit_results: Dict[str, Any],
                               final_report: Dict[str, Any],
                               success: bool, error_message: str = None):
        """
        Store work order processing record.

        Args:
            order_id: Work order ID
            intent: Parsed intent
            tool_results: Tool execution results
            audit_results: Audit results
            final_report: Final report
            success: Whether processing was successful
            error_message: Error message if failed
        """
        conn = sqlite3.connect(self.sqlite_db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO work_order_records
            (order_id, intent_type, intent_subtype, entities, tool_results,
             audit_results, final_report, success, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            order_id,
            intent.get("intent_level_1", "unknown"),
            intent.get("intent_level_2", "unknown"),
            json.dumps(intent.get("entities", [])),
            json.dumps(tool_results),
            json.dumps(audit_results),
            json.dumps(final_report),
            success,
            error_message
        ))

        conn.commit()
        conn.close()

    def get_similar_cases(self, query: str, intent_type: str,
                         limit: int = 3) -> List[Dict[str, Any]]:
        """
        Retrieve similar historical cases.

        Args:
            query: Query text
            intent_type: Intent type for filtering
            limit: Maximum number of cases to return

        Returns:
            List of similar cases
        """
        # Search in vector store
        results = self.case_collection.query(
            query_texts=[query],
            n_results=limit,
            where={"intent_type": intent_type} if intent_type != "all" else None
        )

        cases = []
        if results['documents']:
            for i, doc in enumerate(results['documents'][0]):
                cases.append({
                    "content": doc,
                    "metadata": results['metadatas'][0][i] if results['metadatas'] else {},
                    "distance": results['distances'][0][i] if results['distances'] else None
                })

        return cases

    def get_similar_cases_enhanced(self, query: str, intent_type: str,
                                  limit: int = 3,
                                  strategy: str = RetrievalStrategy.HYBRID,
                                  min_quality: str = CaseQuality.FAIR.value if CASE_ENHANCER_AVAILABLE else None) -> List[Dict[str, Any]]:
        """
        Enhanced similar cases retrieval with multiple strategies.

        Args:
            query: Query text
            intent_type: Intent type for filtering
            limit: Maximum number of cases to return
            strategy: Retrieval strategy (semantic/keyword/hybrid/metadata)
            min_quality: Minimum quality level to filter cases

        Returns:
            List of similar cases with enhanced information
        """
        if not CASE_ENHANCER_AVAILABLE:
            # Fall back to basic retrieval
            return self.get_similar_cases(query, intent_type, limit)

        # Build where clause based on strategy and quality filter
        where_clause = {}
        if intent_type and intent_type != "all":
            where_clause["intent_type"] = intent_type

        if min_quality:
            # Map quality level to score range
            quality_ranges = {
                CaseQuality.EXCELLENT.value: {"$gte": 0.8},
                CaseQuality.GOOD.value: {"$gte": 0.6},
                CaseQuality.FAIR.value: {"$gte": 0.4},
                CaseQuality.POOR.value: {"$gte": 0.0}
            }
            if min_quality in quality_ranges:
                where_clause["quality_score"] = quality_ranges[min_quality]

        # Adjust search based on strategy
        n_results = limit * 2 if strategy == RetrievalStrategy.HYBRID else limit

        # Search in vector store
        results = self.case_collection.query(
            query_texts=[query],
            n_results=n_results,
            where=where_clause if where_clause else None
        )

        cases = []
        if results['documents']:
            for i, doc in enumerate(results['documents'][0]):
                case_data = {
                    "content": doc,
                    "metadata": results['metadatas'][0][i] if results['metadatas'] else {},
                    "distance": results['distances'][0][i] if results['distances'] else None,
                    "relevance_score": 0.0,
                    "match_type": strategy
                }

                # Calculate additional relevance score
                if strategy == RetrievalStrategy.HYBRID:
                    # Combine semantic distance with keyword matching
                    semantic_score = 1.0 - (case_data["distance"] if case_data["distance"] else 0.5)
                    keyword_score = self._calculate_keyword_match(query, doc)
                    case_data["relevance_score"] = (semantic_score * 0.6 + keyword_score * 0.4)
                elif strategy == RetrievalStrategy.SEMANTIC:
                    case_data["relevance_score"] = 1.0 - (case_data["distance"] if case_data["distance"] else 0.5)
                elif strategy == RetrievalStrategy.KEYWORD:
                    case_data["relevance_score"] = self._calculate_keyword_match(query, doc)
                else:  # METADATA or default
                    case_data["relevance_score"] = 0.5

                cases.append(case_data)

        # Sort by relevance score
        cases.sort(key=lambda x: x["relevance_score"], reverse=True)

        # Apply limit after sorting
        return cases[:limit]

    def _calculate_keyword_match(self, query: str, document: str) -> float:
        """
        Calculate keyword match score.

        Args:
            query: Query text
            document: Document text

        Returns:
            Keyword match score (0.0 to 1.0)
        """
        # Extract keywords from query
        query_words = set(re.findall(r'\b\w+\b', query.lower()))
        doc_words = set(re.findall(r'\b\w+\b', document.lower()))

        if not query_words:
            return 0.5

        # Calculate Jaccard similarity
        intersection = query_words.intersection(doc_words)
        union = query_words.union(doc_words)

        if not union:
            return 0.0

        return len(intersection) / len(union)

    def search_sop(self, query: str, limit: int = 2) -> List[Dict[str, Any]]:
        """
        Search SOP manuals.

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            List of SOP items
        """
        results = self.sop_collection.query(
            query_texts=[query],
            n_results=limit
        )

        sops = []
        if results['documents']:
            for i, doc in enumerate(results['documents'][0]):
                sops.append({
                    "content": doc,
                    "metadata": results['metadatas'][0][i] if results['metadatas'] else {},
                    "distance": results['distances'][0][i] if results['distances'] else None
                })

        return sops

    def search_faq(self, query: str, limit: int = 3) -> List[Dict[str, Any]]:
        """
        Search FAQs.

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            List of FAQ items
        """
        results = self.faq_collection.query(
            query_texts=[query],
            n_results=limit
        )

        faqs = []
        if results['documents']:
            for i, doc in enumerate(results['documents'][0]):
                faqs.append({
                    "content": doc,
                    "metadata": results['metadatas'][0][i] if results['metadatas'] else {},
                    "distance": results['distances'][0][i] if results['distances'] else None
                })

        return faqs

    def record_tool_usage(self, tool_name: str, success: bool,
                         execution_time_ms: int):
        """
        Record tool usage statistics.

        Args:
            tool_name: Name of the tool
            success: Whether tool call was successful
            execution_time_ms: Execution time in milliseconds
        """
        conn = sqlite3.connect(self.sqlite_db_path)
        cursor = conn.cursor()

        # Get current stats
        cursor.execute(
            "SELECT success_count, failure_count, total_time_ms FROM tool_usage_stats WHERE tool_name = ?",
            (tool_name,)
        )
        row = cursor.fetchone()

        if row:
            success_count, failure_count, total_time = row
            if success:
                success_count += 1
            else:
                failure_count += 1
            total_time += execution_time_ms

            cursor.execute("""
                UPDATE tool_usage_stats
                SET success_count = ?, failure_count = ?, total_time_ms = ?, last_used = CURRENT_TIMESTAMP
                WHERE tool_name = ?
            """, (success_count, failure_count, total_time, tool_name))
        else:
            success_count = 1 if success else 0
            failure_count = 0 if success else 1
            total_time = execution_time_ms

            cursor.execute("""
                INSERT INTO tool_usage_stats (tool_name, success_count, failure_count, total_time_ms, last_used)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (tool_name, success_count, failure_count, total_time))

        conn.commit()
        conn.close()

    def get_tool_stats(self, tool_name: str = None) -> Dict[str, Any]:
        """
        Get tool usage statistics.

        Args:
            tool_name: Optional specific tool name

        Returns:
            Tool statistics
        """
        conn = sqlite3.connect(self.sqlite_db_path)
        cursor = conn.cursor()

        if tool_name:
            cursor.execute(
                "SELECT * FROM tool_usage_stats WHERE tool_name = ?",
                (tool_name,)
            )
            row = cursor.fetchone()

            if row:
                stats = {
                    "tool_name": row[0],
                    "success_count": row[1],
                    "failure_count": row[2],
                    "total_time_ms": row[3],
                    "last_used": row[4],
                    "success_rate": row[1] / (row[1] + row[2]) if (row[1] + row[2]) > 0 else 0,
                    "avg_time_ms": row[3] / (row[1] + row[2]) if (row[1] + row[2]) > 0 else 0
                }
            else:
                stats = {"error": "Tool not found"}

        else:
            cursor.execute("SELECT * FROM tool_usage_stats")
            rows = cursor.fetchall()

            stats = {}
            for row in rows:
                tool_stats = {
                    "success_count": row[1],
                    "failure_count": row[2],
                    "total_time_ms": row[3],
                    "last_used": row[4],
                    "success_rate": row[1] / (row[1] + row[2]) if (row[1] + row[2]) > 0 else 0,
                    "avg_time_ms": row[3] / (row[1] + row[2]) if (row[1] + row[2]) > 0 else 0
                }
                stats[row[0]] = tool_stats

        conn.close()
        return stats

    def load_sample_data(self):
        """Load sample data for demonstration."""
        # Sample SOPs
        sample_sops = [
            {
                "document": "采购订单处理SOP：1. 接收采购申请 2. 验证供应商信息 3. 创建采购订单 4. 提交审批 5. 跟踪订单状态 6. 验收货物",
                "metadata": {"category": "procurement", "version": "2.0"}
            },
            {
                "document": "物流异常处理SOP：1. 识别异常（延迟、损坏、丢失）2. 通知相关方 3. 调查原因 4. 制定解决方案 5. 执行解决方案 6. 记录经验教训",
                "metadata": {"category": "logistics", "version": "1.5"}
            },
            {
                "document": "质量检验SOP：1. 准备检验设备 2. 抽样检查 3. 记录检验结果 4. 判断合格/不合格 5. 生成检验报告 6. 归档记录",
                "metadata": {"category": "quality", "version": "3.1"}
            }
        ]

        for sop in sample_sops:
            self.sop_collection.add(
                documents=[sop["document"]],
                metadatas=[sop["metadata"]],
                ids=[hashlib.md5(sop["document"].encode()).hexdigest()[:12]]
            )

        # Sample FAQs
        sample_faqs = [
            {
                "document": "Q: 订单状态有哪些？A: 待付款、待发货、已发货、运输中、已收货、已完成、已取消",
                "metadata": {"category": "order", "tags": "status"}
            },
            {
                "document": "Q: 如何处理物流延迟？A: 1. 联系承运商 2. 更新预计到达时间 3. 通知客户 4. 跟踪货物位置 5. 必要时申请赔偿",
                "metadata": {"category": "logistics", "tags": "delay"}
            },
            {
                "document": "Q: 如何创建质量检验工单？A: 1. 选择检验类型 2. 填写检验项目 3. 指定检验人员 4. 设置截止时间 5. 提交审批",
                "metadata": {"category": "quality", "tags": "inspection"}
            }
        ]

        for faq in sample_faqs:
            self.faq_collection.add(
                documents=[faq["document"]],
                metadatas=[faq["metadata"]],
                ids=[hashlib.md5(faq["document"].encode()).hexdigest()[:12]]
            )

        print("Sample data loaded into long-term memory")

    def add_enhanced_case(self, case: 'HistoricalCase') -> str:
        if not CASE_ENHANCER_AVAILABLE:
            raise ImportError("CaseEnhancer module not available")

        # Enrich case data
        enriched_case = self.case_enhancer.enrich_case_data(case)

        # Convert to vector document
        document, metadata = enriched_case.to_vector_document()

        # Add to vector store
        self.case_collection.add(
            documents=[document],
            metadatas=[metadata],
            ids=[enriched_case.case_id]
        )

        # Also store in SQLite for detailed analysis
        self._store_case_in_sqlite(enriched_case)

        print(f"✅ Enhanced case added: {enriched_case.case_id} (Quality: {enriched_case.quality_level})")
        return enriched_case.case_id

    def _store_case_in_sqlite(self, case: HistoricalCase):
        """Store enhanced case in SQLite database."""
        conn = sqlite3.connect(self.sqlite_db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS enhanced_cases (
                case_id TEXT PRIMARY KEY,
                intent_type TEXT NOT NULL,
                intent_subtype TEXT NOT NULL,
                user_input TEXT NOT NULL,
                agent_response TEXT NOT NULL,
                tools_used TEXT,
                entities_extracted TEXT,
                processing_time_ms INTEGER,
                success BOOLEAN,
                quality_score REAL,
                quality_level TEXT,
                tags TEXT,
                metadata TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            INSERT OR REPLACE INTO enhanced_cases
            (case_id, intent_type, intent_subtype, user_input, agent_response,
             tools_used, entities_extracted, processing_time_ms, success,
             quality_score, quality_level, tags, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            case.case_id,
            case.intent_type,
            case.intent_subtype,
            case.user_input,
            case.agent_response,
            json.dumps(case.tools_used),
            json.dumps(case.entities_extracted),
            case.processing_time_ms,
            case.success,
            case.quality_score,
            case.quality_level,
            json.dumps(case.tags),
            json.dumps(case.metadata)
        ))

        conn.commit()
        conn.close()

    def load_enhanced_sample_data(self):
        """Load enhanced sample data for demonstration."""
        if not CASE_ENHANCER_AVAILABLE:
            print("⚠️ CaseEnhancer not available, using basic sample data")
            self.load_sample_data()
            return

        print("📚 Loading enhanced sample cases...")

        # Generate sample cases using enhancer
        sample_cases = self.case_enhancer.generate_sample_cases()

        added_count = 0
        for case in sample_cases:
            try:
                self.add_enhanced_case(case)
                added_count += 1
            except Exception as e:
                print(f"❌ Failed to add case {case.case_id}: {e}")

        print(f"✅ Loaded {added_count} enhanced sample cases")

        # Also load basic SOP and FAQ data
        self.load_sample_data()

    def get_case_quality_stats(self) -> Dict[str, Any]:
        """
        Get case quality statistics.

        Returns:
            Quality statistics
        """
        if not CASE_ENHANCER_AVAILABLE:
            return {"error": "CaseEnhancer not available"}

        conn = sqlite3.connect(self.sqlite_db_path)
        cursor = conn.cursor()

        # Check if table exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='enhanced_cases'
        """)
        table_exists = cursor.fetchone()

        if not table_exists:
            return {"total_cases": 0, "message": "No enhanced cases table"}

        # Get quality distribution
        cursor.execute("""
            SELECT quality_level, COUNT(*) as count
            FROM enhanced_cases
            GROUP BY quality_level
            ORDER BY
                CASE quality_level
                    WHEN 'excellent' THEN 1
                    WHEN 'good' THEN 2
                    WHEN 'fair' THEN 3
                    WHEN 'poor' THEN 4
                    ELSE 5
                END
        """)
        quality_distribution = dict(cursor.fetchall())

        # Get average quality score
        cursor.execute("SELECT AVG(quality_score) FROM enhanced_cases")
        avg_score_result = cursor.fetchone()
        avg_score = avg_score_result[0] if avg_score_result[0] else 0.0

        # Get success rate
        cursor.execute("SELECT success, COUNT(*) FROM enhanced_cases GROUP BY success")
        success_stats = cursor.fetchall()
        success_count = 0
        total_count = 0
        for success, count in success_stats:
            total_count += count
            if success:
                success_count += count

        success_rate = success_count / total_count if total_count > 0 else 0.0

        # Get intent distribution
        cursor.execute("""
            SELECT intent_type, intent_subtype, COUNT(*) as count
            FROM enhanced_cases
            GROUP BY intent_type, intent_subtype
            ORDER BY count DESC
        """)
        intent_distribution = cursor.fetchall()

        conn.close()

        return {
            "total_cases": total_count,
            "success_rate": round(success_rate * 100, 1),
            "average_quality_score": round(avg_score, 3),
            "quality_distribution": quality_distribution,
            "intent_distribution": [
                {
                    "intent_type": intent_type,
                    "intent_subtype": intent_subtype,
                    "count": count
                }
                for intent_type, intent_subtype, count in intent_distribution
            ],
            "updated_at": datetime.now().isoformat()
        }


class MemoryManager:
    """
    Manages all three memory layers.
    """

    def __init__(self):
        self.short_term = ShortTermMemory(
            window_size=settings.memory_window_size
        )
        self.long_term = LongTermMemory(
            vector_store_path=settings.vector_store_path,
            sqlite_db_path=settings.sqlite_db_path
        )

        # Load enhanced sample data on first run
        try:
            self.long_term.load_enhanced_sample_data()
            print("✅ Enhanced sample data loaded successfully")
        except Exception as e:
            print(f"⚠️ Could not load enhanced data: {e}")
            # Fall back to basic sample data
            try:
                self.long_term.load_sample_data()
                print("✅ Basic sample data loaded successfully")
            except Exception as e2:
                print(f"❌ Could not load any sample data: {e2}")

    def record_agent_action(self, agent_name: str, action: str,
                           details: Dict[str, Any], importance: float = 0.5):
        """
        Record agent action in short-term memory.

        Args:
            agent_name: Name of the agent
            action: Action performed
            details: Action details
            importance: Importance score
        """
        content = {
            "agent": agent_name,
            "action": action,
            "details": details,
            "timestamp": time.time()
        }

        tags = [agent_name, action]
        if "intent" in details:
            tags.append(details["intent"])

        self.short_term.add(content, tags, importance)

    def get_context_summary(self) -> str:
        """
        Get summary of current context from all memory layers.

        Returns:
            Context summary
        """
        short_term_summary = self.short_term.get_summary()

        summary_parts = [
            "## 当前上下文",
            f"**短期记忆**: {short_term_summary}",
            "**长期记忆**: 已加载SOP手册和FAQ知识库"
        ]

        return "\n".join(summary_parts)

    def retrieve_relevant_knowledge(self, query: str,
                                   intent_type: str) -> Dict[str, Any]:
        """
        Retrieve relevant knowledge from long-term memory.

        Args:
            query: Query text
            intent_type: Intent type

        Returns:
            Retrieved knowledge
        """
        knowledge = {
            "sops": self.long_term.search_sop(query, limit=2),
            "faqs": self.long_term.search_faq(query, limit=3),
            "similar_cases": self.long_term.get_similar_cases(query, intent_type, limit=2)
        }

        return knowledge

    def format_knowledge_for_prompt(self, knowledge: Dict[str, Any]) -> str:
        """
        Format retrieved knowledge for LLM prompt.

        Args:
            knowledge: Retrieved knowledge

        Returns:
            Formatted knowledge text
        """
        sections = []

        if knowledge["sops"]:
            sections.append("### 相关SOP:")
            for i, sop in enumerate(knowledge["sops"], 1):
                sections.append(f"{i}. {sop['content']}")

        if knowledge["faqs"]:
            sections.append("### 相关FAQ:")
            for i, faq in enumerate(knowledge["faqs"], 1):
                sections.append(f"{i}. {faq['content']}")

        if knowledge["similar_cases"]:
            sections.append("### 类似历史案例:")
            for i, case in enumerate(knowledge["similar_cases"], 1):
                sections.append(f"{i}. {case['content']}")

        if not sections:
            return "无相关历史知识"

        return "\n".join(sections)


# Global memory manager instance
memory_manager = MemoryManager()