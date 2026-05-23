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

    def __init__(self, vector_store_path: str = "./supply_chain_agent/data/vector_store",
                 sqlite_db_path: str = "./supply_chain_agent/data/agent_memory.db"):
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

    def load_sop_documents(self, sop_dir: str = None) -> int:
        """
        Load SOP documents from directory into vector store.

        Args:
            sop_dir: Directory containing SOP markdown files (default: dataset/SOPData)

        Returns:
            Number of document chunks loaded
        """
        import os

        if sop_dir is None:
            # Default to dataset/SOPData relative to project root
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            sop_dir = os.path.join(project_root, "dataset", "SOPData")

        if not os.path.exists(sop_dir):
            print(f"⚠️ SOP directory not found: {sop_dir}")
            return 0

        print(f"Loading SOP documents from {sop_dir}...")

        chunk_count = 0

        for filename in os.listdir(sop_dir):
            if not filename.endswith('.md'):
                continue

            filepath = os.path.join(sop_dir, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Split document into chunks
                chunks = self._split_document(content, max_chunk_size=1000, overlap=100)

                for i, chunk in enumerate(chunks):
                    if not chunk.strip():
                        continue

                    # Generate unique ID
                    chunk_id = hashlib.md5(f"{filename}_{i}".encode()).hexdigest()[:12]

                    # Add to vector store
                    self.sop_collection.add(
                        documents=[chunk],
                        metadatas=[{
                            "source": filename,
                            "chunk_id": i,
                            "doc_type": "sop",
                            "total_chunks": len(chunks)
                        }],
                        ids=[chunk_id]
                    )
                    chunk_count += 1

                print(f"  ✓ Loaded {filename}: {len(chunks)} chunks")

            except Exception as e:
                print(f"  ❌ Failed to load {filename}: {e}")

        print(f"✅ Total SOP chunks loaded: {chunk_count}")
        return chunk_count

    def _split_document(self, content: str, max_chunk_size: int = 1000, overlap: int = 100) -> List[str]:
        """
        Split document into overlapping chunks.

        Args:
            content: Document content
            max_chunk_size: Maximum chunk size in characters
            overlap: Overlap between chunks

        Returns:
            List of document chunks
        """
        if len(content) <= max_chunk_size:
            return [content]

        chunks = []
        start = 0

        while start < len(content):
            end = start + max_chunk_size

            # Try to find a natural break point
            if end < len(content):
                # Look for paragraph break
                break_point = content.rfind('\n\n', start, end)
                if break_point == -1:
                    # Look for sentence break
                    break_point = content.rfind('。', start, end)
                    if break_point == -1:
                        break_point = content.rfind('\n', start, end)

                if break_point > start:
                    end = break_point + 1

            chunk = content[start:end].strip()
            if chunk:
                chunks.append(chunk)

            start = end - overlap if end < len(content) else end

        return chunks

    def has_sop_data(self) -> bool:
        """Check if SOP collection has data."""
        try:
            count = self.sop_collection.count()
            return count > 0
        except:
            return False


class MemoryManager:
    """
    Manages all three memory layers.
    """

    def __init__(self, load_sop_on_init: bool = True):
        self.short_term = ShortTermMemory(
            window_size=settings.memory_window_size
        )
        self.long_term = LongTermMemory(
            vector_store_path=settings.vector_store_path,
            sqlite_db_path=settings.sqlite_db_path
        )

        # Check if SOP data is already loaded
        if load_sop_on_init:
            if not self.long_term.has_sop_data():
                print("⚠️ No SOP data found in vector store. Run data initialization.")
            else:
                print("✅ SOP data already loaded in vector store")

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
            "faqs": self.long_term.search_faq(query, limit=3)
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

        if not sections:
            return "无相关历史知识"

        return "\n".join(sections)


# Global memory manager instance
memory_manager = MemoryManager()