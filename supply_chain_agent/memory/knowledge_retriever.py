"""
Knowledge Retriever for fallback responses.

Searches ChromaDB for relevant SOP/FAQ when tools are unavailable.
"""

from typing import Dict, Any, List, Optional
import chromadb
from chromadb.config import Settings as ChromaSettings

from supply_chain_agent.config import settings


class KnowledgeRetriever:
    """知识库检索器，用于降级响应时检索相关SOP/FAQ"""

    def __init__(self, persist_directory: Optional[str] = None):
        """
        初始化知识库检索器

        Args:
            persist_directory: ChromaDB持久化目录
        """
        self.persist_directory = persist_directory or settings.vector_store_path

        try:
            self.client = chromadb.PersistentClient(
                path=self.persist_directory,
                settings=ChromaSettings(anonymized_telemetry=False)
            )
            # 尝试获取或创建集合
            self.collection = self.client.get_or_create_collection(
                name="knowledge_base",
                metadata={"description": "SOP and FAQ knowledge base"}
            )
        except Exception as e:
            print(f"⚠️ Failed to initialize ChromaDB: {e}")
            self.client = None
            self.collection = None

    async def search(
        self,
        query: str,
        top_k: int = 3,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        搜索知识库

        Args:
            query: 查询文本
            top_k: 返回结果数量
            filters: 元数据过滤条件

        Returns:
            相关知识条目列表
        """
        if self.collection is None:
            return []

        try:
            # 构建where条件
            where = filters if filters else None

            # 执行查询
            results = self.collection.query(
                query_texts=[query],
                n_results=top_k,
                where=where,
                include=["documents", "metadatas", "distances"]
            )

            # 格式化结果
            knowledge_items = []
            if results["documents"] and results["documents"][0]:
                for i, doc in enumerate(results["documents"][0]):
                    item = {
                        "content": doc,
                        "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                        "distance": results["distances"][0][i] if results["distances"] else 0.0,
                    }
                    knowledge_items.append(item)

            return knowledge_items

        except Exception as e:
            print(f"⚠️ Knowledge search failed: {e}")
            return []

    async def search_sop(self, query: str, top_k: int = 2) -> List[Dict[str, Any]]:
        """搜索SOP流程文档"""
        return await self.search(
            query=query,
            top_k=top_k,
            filters={"type": "sop"}
        )

    async def search_faq(self, query: str, top_k: int = 2) -> List[Dict[str, Any]]:
        """搜索FAQ"""
        return await self.search(
            query=query,
            top_k=top_k,
            filters={"type": "faq"}
        )

    def add_knowledge(
        self,
        documents: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        ids: Optional[List[str]] = None
    ) -> bool:
        """
        添加知识到知识库

        Args:
            documents: 文档内容列表
            metadatas: 元数据列表
            ids: 文档ID列表

        Returns:
            是否成功
        """
        if self.collection is None:
            return False

        try:
            # 生成ID（如果没有提供）
            if ids is None:
                import hashlib
                ids = [hashlib.md5(doc.encode()).hexdigest() for doc in documents]

            self.collection.add(
                documents=documents,
                metadatas=metadatas,
                ids=ids
            )
            return True
        except Exception as e:
            print(f"⚠️ Failed to add knowledge: {e}")
            return False

    def get_stats(self) -> Dict[str, Any]:
        """获取知识库统计信息"""
        if self.collection is None:
            return {"status": "unavailable"}

        try:
            count = self.collection.count()
            return {
                "status": "available",
                "document_count": count,
                "collection_name": self.collection.name
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}


# 单例实例
_knowledge_retriever: Optional[KnowledgeRetriever] = None


def get_knowledge_retriever() -> KnowledgeRetriever:
    """获取知识库检索器单例"""
    global _knowledge_retriever

    if _knowledge_retriever is None:
        _knowledge_retriever = KnowledgeRetriever()

    return _knowledge_retriever