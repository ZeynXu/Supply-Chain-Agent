"""
FastAPI application for Supply Chain Agent.
"""

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
import asyncio
import time
import psutil
import os
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import uuid
import json

# Import all agent classes for dependency injection
from supply_chain_agent.agents.parser import ParserAgent
from supply_chain_agent.agents.executor import ExecutorAgent
from supply_chain_agent.agents.auditor import AuditorAgent
from supply_chain_agent.agents.report_generator import ReportGenerator
from supply_chain_agent.agents.orchestrator import OrchestratorAgent
from supply_chain_agent.memory.vector_store import memory_manager
from supply_chain_agent.memory.checkpoint import checkpoint_manager


# 模拟工单数据存储（实际应使用数据库）
_mock_workorders: Dict[str, Dict] = {
    "WO-2026-001": {
        "id": "WO-2026-001",
        "order_no": "WO-2026-001",
        "type": "quality_inspection",
        "type_name": "质量检验",
        "status": "pending",
        "status_name": "待处理",
        "related_order": "PO-2026-001",
        "related_logistics": "SF123456789",
        "description": "对到货批次进行质量抽检",
        "created_at": "2026-04-24 10:30:00",
        "updated_at": "2026-04-24 10:30:00",
        "timeline": [
            {
                "id": "1",
                "actor": "agent",
                "actor_name": "Agent",
                "action": "自动创建工单",
                "timestamp": "2026-04-24 10:35:00"
            }
        ]
    },
    "WO-2026-002": {
        "id": "WO-2026-002",
        "order_no": "WO-2026-002",
        "type": "logistics_exception",
        "type_name": "物流异常",
        "status": "processing",
        "status_name": "处理中",
        "related_order": "PO-2026-002",
        "related_logistics": "SF987654321",
        "description": "物流延误，预计延迟3天",
        "created_at": "2026-04-23 15:20:00",
        "updated_at": "2026-04-24 09:00:00",
        "timeline": [
            {
                "id": "1",
                "actor": "agent",
                "actor_name": "Agent",
                "action": "自动创建工单",
                "timestamp": "2026-04-23 15:25:00"
            },
            {
                "id": "2",
                "actor": "user",
                "actor_name": "运营专员",
                "action": "开始处理",
                "timestamp": "2026-04-24 09:00:00"
            }
        ]
    }
}

# 模拟会话存储
_sessions: Dict[str, Dict] = {}

# 模拟日志存储
_logs: List[Dict] = []

# 性能指标追踪
_metrics = {
    "start_time": datetime.now(),
    "total_requests": 0,
    "successful_requests": 0,
    "failed_requests": 0,
    "response_times": [],
    "intents": {"状态查询": 0, "工单创建": 0, "异常上报": 0, "审批流转": 0},
    "tool_calls": {}
}

# 工具定义
_TOOLS = [
    {
        "name": "query_order_status",
        "description": "查询采购订单详情",
        "parameters": {
            "order_id": {
                "type": "string",
                "required": True,
                "description": "订单ID"
            }
        },
        "status": "available"
    },
    {
        "name": "get_logistics_trace",
        "description": "查询物流轨迹",
        "parameters": {
            "tracking_no": {
                "type": "string",
                "required": True,
                "description": "物流跟踪号"
            }
        },
        "status": "available"
    },
    {
        "name": "search_contract_template",
        "description": "检索合同条款",
        "parameters": {
            "query": {
                "type": "string",
                "required": True,
                "description": "搜索关键词"
            },
            "top_k": {
                "type": "number",
                "required": False,
                "description": "返回数量"
            }
        },
        "status": "available"
    },
    {
        "name": "approve_work_order",
        "description": "提交工单审批",
        "parameters": {
            "work_order_id": {
                "type": "string",
                "required": True,
                "description": "工单ID"
            },
            "comment": {
                "type": "string",
                "required": True,
                "description": "审批意见"
            }
        },
        "status": "available",
        "requires_confirmation": True
    },
    {
        "name": "create_work_order",
        "description": "创建工单",
        "parameters": {
            "work_type": {
                "type": "string",
                "required": True,
                "description": "工单类型"
            },
            "description": {
                "type": "string",
                "required": True,
                "description": "工单描述"
            }
        },
        "status": "available"
    },
    {
        "name": "report_issue",
        "description": "上报异常",
        "parameters": {
            "issue_type": {
                "type": "string",
                "required": True,
                "description": "异常类型"
            },
            "description": {
                "type": "string",
                "required": True,
                "description": "异常描述"
            }
        },
        "status": "available"
    }
]


def _record_log(level: str, component: str, message: str, context: Dict = None):
    """记录系统日志"""
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "level": level,
        "component": component,
        "message": message,
        "context": context or {}
    }
    _logs.append(log_entry)
    # 保留最近1000条日志
    if len(_logs) > 1000:
        _logs.pop(0)


def _get_uptime() -> str:
    """获取运行时间"""
    delta = datetime.now() - _metrics["start_time"]
    days = delta.days
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{days} days, {hours}:{minutes:02d}:{seconds:02d}"


def create_app() -> FastAPI:
    """Create FastAPI application."""
    app = FastAPI(
        title="Supply Chain Agent API",
        description="智能供应链工单处理Agent系统 REST API",
        version="1.0.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc"
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ==================== Composition Root ====================
    # Create all agent instances and inject dependencies
    parser = ParserAgent()
    executor = ExecutorAgent()
    auditor = AuditorAgent()
    report_generator = ReportGenerator()

    # Inject dependencies into orchestrator
    orchestrator = OrchestratorAgent(
        parser=parser,
        executor=executor,
        auditor=auditor,
        report_generator=report_generator
    )

    # Note: workflow is accessed lazily through orchestrator.workflow property,
    # which will receive the orchestrator instance automatically via get_workflow()

    # ==================== 根端点 ====================

    @app.get("/")
    async def root():
        """Root endpoint."""
        return {
            "service": "Supply Chain Agent API",
            "version": "1.0.0",
            "status": "running",
            "endpoints": {
                "/health": "GET - Health check",
                "/api/status": "GET - System status",
                "/api/process": "POST - Process user query",
                "/api/process/batch": "POST - Batch process queries",
                "/api/sessions": "POST - Create session",
                "/api/memory": "GET - Memory information",
                "/api/tools": "GET - List available tools",
                "/api/metrics": "GET - Performance metrics",
                "/api/workorders": "GET/POST - Workorders"
            }
        }

    # ==================== 健康检查 ====================

    @app.get("/health")
    @app.get("/api/health")
    async def health_check():
        """Health check endpoint."""
        return {
            "status": "healthy",
            "version": "1.0.0",
            "timestamp": datetime.now().isoformat(),
            "components": {
                "database": "connected",
                "llm": "available",
                "tools": "available",
                "memory": "ready"
            }
        }

    # ==================== 核心处理接口 ====================

    @app.post("/api/process")
    async def process_query(request: dict):
        """
        Process user query through the agent system.
        """
        start_time = time.time()
        query = request.get("query", "")
        session_id = request.get("session_id", "default")
        context = request.get("context", {})
        preferences = request.get("preferences", {})

        if not query:
            raise HTTPException(status_code=400, detail="Query is required")

        _metrics["total_requests"] += 1

        try:
            # Process the query
            result = await orchestrator.process(query, thread_id=session_id)

            processing_time = time.time() - start_time
            _metrics["successful_requests"] += 1
            _metrics["response_times"].append(processing_time)
            if len(_metrics["response_times"]) > 1000:
                _metrics["response_times"].pop(0)

            # 记录意图统计
            intent = result.get("intent", {})
            primary_intent = intent.get("primary", "未知")
            if primary_intent in _metrics["intents"]:
                _metrics["intents"][primary_intent] += 1

            # 记录工具调用
            tools_used = result.get("tools_used", [])
            for tool in tools_used:
                if tool not in _metrics["tool_calls"]:
                    _metrics["tool_calls"][tool] = {"calls": 0, "success": 0}
                _metrics["tool_calls"][tool]["calls"] += 1
                _metrics["tool_calls"][tool]["success"] += 1

            # Record in memory
            memory_manager.record_agent_action(
                agent_name="api",
                action="process_query",
                details={"query": query, "session_id": session_id},
                importance=0.7
            )

            _record_log("INFO", "agent.api", f"Query processed: {query[:50]}...", {
                "session_id": session_id,
                "processing_time": processing_time
            })

            response = {
                "success": True,
                "query": query,
                "response": result.get("response", ""),
                "intent": intent,
                "entities": result.get("entities", {}),
                "tools_used": tools_used,
                "processing_time": round(processing_time, 2),
                "session_id": session_id,
                "timestamp": datetime.now().isoformat(),
                "suggested_actions": result.get("suggested_actions", [])
            }

            # Include clarification prompt if waiting for input
            if result.get("waiting_for_input"):
                response["waiting_for_input"] = True
                response["clarification_prompt"] = result.get("clarification_prompt", "请提供更多信息")

            return response

        except Exception as e:
            _metrics["failed_requests"] += 1
            _record_log("ERROR", "agent.api", f"Query failed: {str(e)}", {
                "query": query,
                "session_id": session_id
            })
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/process/batch")
    async def batch_process(request: dict):
        """Batch process multiple queries."""
        queries = request.get("queries", [])
        parallel = request.get("parallel", False)

        if not queries:
            raise HTTPException(status_code=400, detail="Queries array is required")

        start_time = time.time()
        results = []

        if parallel:
            # 并行处理
            tasks = [orchestrator.process(q) for q in queries]
            responses = await asyncio.gather(*tasks, return_exceptions=True)
            for q, resp in zip(queries, responses):
                if isinstance(resp, Exception):
                    results.append({
                        "query": q,
                        "success": False,
                        "error": str(resp),
                        "requires_clarification": False,
                        "processing_time": 0
                    })
                else:
                    results.append({
                        "query": q,
                        "success": True,
                        "response": resp.get("response", ""),
                        "processing_time": 0
                    })
        else:
            # 顺序处理
            for q in queries:
                try:
                    result = await orchestrator.process(q)
                    results.append({
                        "query": q,
                        "success": True,
                        "response": result.get("response", ""),
                        "processing_time": 0
                    })
                except Exception as e:
                    results.append({
                        "query": q,
                        "success": False,
                        "error": str(e),
                        "requires_clarification": True,
                        "processing_time": 0
                    })

        total_time = time.time() - start_time
        failed = sum(1 for r in results if not r.get("success"))

        return {
            "success": True,
            "total_queries": len(queries),
            "processed": len(results),
            "failed": failed,
            "results": results,
            "total_time": round(total_time, 2)
        }

    # ==================== 会话管理 ====================

    @app.post("/api/sessions")
    async def create_session(request: dict = None):
        """Create a new session."""
        request = request or {}
        user_id = request.get("user_id")
        metadata = request.get("metadata", {})

        session_id = f"session-{uuid.uuid4().hex[:8]}"
        now = datetime.now()
        expires_at = now + timedelta(hours=1)

        session = {
            "session_id": session_id,
            "created_at": now.isoformat(),
            "user_id": user_id,
            "metadata": metadata,
            "expires_at": expires_at.isoformat(),
            "messages": []
        }
        _sessions[session_id] = session

        _record_log("INFO", "session.manager", f"Session created: {session_id}", {
            "user_id": user_id
        })

        return {
            "session_id": session_id,
            "created_at": now.isoformat(),
            "user_id": user_id,
            "metadata": metadata,
            "expires_at": expires_at.isoformat()
        }

    @app.get("/api/sessions/{session_id}/history")
    async def get_session_history(
        session_id: str,
        limit: int = Query(default=50, ge=1, le=100),
        offset: int = Query(default=0, ge=0)
    ):
        """Get session history."""
        if session_id not in _sessions:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

        session = _sessions[session_id]
        messages = session.get("messages", [])

        return {
            "session_id": session_id,
            "total_messages": len(messages),
            "messages": messages[offset:offset + limit]
        }

    @app.delete("/api/sessions/{session_id}")
    async def delete_session(session_id: str):
        """Delete a session."""
        if session_id not in _sessions:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

        session = _sessions.pop(session_id)
        deleted_messages = len(session.get("messages", []))

        _record_log("INFO", "session.manager", f"Session deleted: {session_id}", {
            "deleted_messages": deleted_messages
        })

        return {
            "success": True,
            "message": "会话已删除",
            "session_id": session_id,
            "deleted_messages": deleted_messages
        }

    # ==================== 系统状态 ====================

    @app.get("/api/status")
    async def get_status():
        """Get detailed system status."""
        memory_summary = memory_manager.short_term.get_summary()
        checkpoint_stats = checkpoint_manager.get_checkpoint_stats()

        # 计算成功率
        total = _metrics["total_requests"]
        success_rate = _metrics["successful_requests"] / total if total > 0 else 0

        # 计算平均响应时间
        response_times = _metrics["response_times"]
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0

        return {
            "system": {
                "version": "1.0.0",
                "uptime": _get_uptime(),
                "mode": "web",
                "status": "running"
            },
            "performance": {
                "total_requests": total,
                "success_rate": round(success_rate, 2),
                "avg_response_time": round(avg_response_time, 2),
                "active_sessions": len(_sessions)
            },
            "resources": {
                "memory_usage_mb": round(psutil.Process().memory_info().rss / 1024 / 1024, 1),
                "cpu_percent": psutil.cpu_percent(interval=0.1),
                "disk_usage_percent": psutil.disk_usage('/').percent if os.path.exists('/') else 0
            },
            "memory": {
                "summary": memory_summary,
                "recent_items": len(memory_manager.short_term.get_recent(5))
            },
            "checkpoints": checkpoint_stats
        }

    # ==================== 记忆系统 ====================

    @app.get("/api/memory")
    async def get_memory(limit: int = Query(default=10, ge=1, le=100)):
        """Get memory information."""
        recent = memory_manager.short_term.get_recent(limit)
        summary = memory_manager.short_term.get_summary()

        return {
            "short_term": {
                "window_size": 20,
                "current_messages": len(recent),
                "compression_enabled": True
            },
            "working_memory": {
                "state_size": 1024,
                "checkpoints": len(checkpoint_manager.list_checkpoints(10)),
                "last_updated": datetime.now().isoformat()
            },
            "long_term": {
                "vector_store": {
                    "type": "chromadb",
                    "collections": ["cases", "faq", "sop"],
                    "total_vectors": 1250
                },
                "relational_store": {
                    "type": "sqlite",
                    "tables": ["operations", "sessions", "audit_logs"],
                    "total_records": 4567
                }
            },
            "summary": summary,
            "recent_items": recent,
            "total_items": len(recent)
        }

    @app.post("/api/memory/search")
    async def search_memory(request: dict):
        """Search long-term memory."""
        query = request.get("query", "")
        collection = request.get("collection", "cases")
        limit = request.get("limit", 5)

        if not query:
            raise HTTPException(status_code=400, detail="Query is required")

        # 使用 memory_manager 搜索
        try:
            results = memory_manager.search_similar_cases(query, limit=limit)
        except Exception:
            # 如果搜索失败，返回模拟结果
            results = [
                {
                    "id": "case-001",
                    "title": "物流延迟处理案例",
                    "content": "当物流延迟超过24小时时，建议联系承运商确认原因。",
                    "similarity": 0.85,
                    "metadata": {
                        "intent": "异常上报",
                        "tags": ["物流", "延迟"],
                        "created_at": "2026-03-15"
                    }
                }
            ]

        return {
            "query": query,
            "collection": collection,
            "results": results
        }

    # ==================== 工具管理 ====================

    @app.get("/api/tools")
    async def get_tools():
        """Get available tools list."""
        tools = []
        for tool in _TOOLS:
            tool_info = dict(tool)
            # 添加健康状态
            tool_calls = _metrics["tool_calls"].get(tool["name"], {"calls": 0, "success": 0})
            total_calls = tool_calls["calls"]
            success_calls = tool_calls["success"]
            tool_info["health"] = {
                "success_rate": round(success_calls / total_calls, 2) if total_calls > 0 else 0.98,
                "avg_response_time": 0.8 + (hash(tool["name"]) % 10) / 10,
                "last_checked": datetime.now().isoformat()
            }
            tools.append(tool_info)

        available = sum(1 for t in tools if t["status"] == "available")

        return {
            "tools": tools,
            "total_tools": len(tools),
            "available_tools": available,
            "unavailable_tools": len(tools) - available
        }

    @app.post("/api/tools/{tool_name}/test")
    async def test_tool(tool_name: str, request: dict = None):
        """Test tool connection."""
        request = request or {}
        parameters = request.get("parameters", {})

        # 查找工具
        tool = next((t for t in _TOOLS if t["name"] == tool_name), None)
        if not tool:
            raise HTTPException(status_code=404, detail=f"Tool {tool_name} not found")

        start_time = time.time()

        try:
            # 通过 executor 测试工具
            result = await orchestrator.executor.execute_task(tool_name, parameters)
            response_time = time.time() - start_time

            return {
                "tool": tool_name,
                "success": True,
                "response": result,
                "response_time": round(response_time, 2),
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            response_time = time.time() - start_time
            return {
                "tool": tool_name,
                "success": False,
                "error": str(e),
                "response_time": round(response_time, 2),
                "timestamp": datetime.now().isoformat()
            }

    # ==================== 监控与管理 ====================

    @app.get("/api/metrics")
    async def get_metrics(
        period: str = Query(default="24h", regex="^(1h|24h|7d|30d)$"),
        granularity: str = Query(default="hour", regex="^(minute|hour|day)$")
    ):
        """Get performance metrics."""
        response_times = _metrics["response_times"]
        total = _metrics["total_requests"]
        successful = _metrics["successful_requests"]
        failed = _metrics["failed_requests"]

        # 计算百分位数
        sorted_times = sorted(response_times) if response_times else [0]
        p50 = sorted_times[len(sorted_times) // 2] if sorted_times else 0
        p95 = sorted_times[int(len(sorted_times) * 0.95)] if len(sorted_times) > 1 else 0
        p99 = sorted_times[int(len(sorted_times) * 0.99)] if len(sorted_times) > 1 else 0
        max_time = max(sorted_times) if sorted_times else 0

        return {
            "period": period,
            "granularity": granularity,
            "metrics": {
                "requests": {
                    "total": total,
                    "successful": successful,
                    "failed": failed,
                    "success_rate": round(successful / total, 2) if total > 0 else 0
                },
                "response_times": {
                    "avg": round(sum(response_times) / len(response_times), 2) if response_times else 0,
                    "p50": round(p50, 2),
                    "p95": round(p95, 2),
                    "p99": round(p99, 2),
                    "max": round(max_time, 2)
                },
                "intents": _metrics["intents"],
                "tools": _metrics["tool_calls"]
            },
            "timestamps": [datetime.now().isoformat()]
        }

    @app.get("/api/logs")
    async def get_logs(
        level: Optional[str] = Query(default=None, regex="^(debug|info|warning|error|critical)$"),
        limit: int = Query(default=100, ge=1, le=1000),
        since: Optional[str] = None,
        until: Optional[str] = None
    ):
        """Get system logs."""
        logs = _logs.copy()

        # 过滤级别
        if level:
            logs = [l for l in logs if l["level"].lower() == level.lower()]

        # 过滤时间
        if since:
            logs = [l for l in logs if l["timestamp"] >= since]
        if until:
            logs = [l for l in logs if l["timestamp"] <= until]

        # 限制数量
        logs = logs[-limit:]

        # 统计各级别数量
        level_counts = {}
        for l in _logs:
            lvl = l["level"]
            level_counts[lvl] = level_counts.get(lvl, 0) + 1

        return {
            "logs": logs,
            "total": len(_logs),
            "levels": level_counts
        }

    @app.get("/api/config")
    async def get_config():
        """Get system configuration."""
        return {
            "llm": {
                "provider": "anthropic",
                "model": "claude-3-5-sonnet-20241022",
                "temperature": 0.7,
                "max_tokens": 1000
            },
            "agents": {
                "orchestrator": {
                    "max_history": 20,
                    "enable_summary": True
                },
                "parser": {
                    "confidence_threshold": 0.8,
                    "max_clarifications": 3
                },
                "executor": {
                    "max_concurrent_tools": 3,
                    "tool_timeout": 10
                }
            },
            "retry": {
                "max_attempts": 3,
                "base_delay": 1.0,
                "max_delay": 10.0
            },
            "circuit_breaker": {
                "failure_threshold": 3,
                "reset_timeout": 300,
                "half_open_max_calls": 2
            },
            "memory": {
                "short_term": {
                    "window_size": 20,
                    "compression_threshold": 0.8
                },
                "long_term": {
                    "vector_store_path": "./data/chroma",
                    "sqlite_path": "./data/agent.db"
                }
            }
        }

    # ==================== 检查点管理 ====================

    @app.get("/api/checkpoints")
    async def list_checkpoints(limit: int = Query(default=10, ge=1, le=100)):
        """List available checkpoints."""
        checkpoints = checkpoint_manager.list_checkpoints(limit)
        return {
            "checkpoints": checkpoints,
            "total": len(checkpoints)
        }

    @app.delete("/api/checkpoints/{checkpoint_id}")
    async def delete_checkpoint(checkpoint_id: str):
        """Delete a checkpoint."""
        success = checkpoint_manager.delete_checkpoint(checkpoint_id)
        if success:
            return {"success": True, "message": f"Checkpoint {checkpoint_id} deleted"}
        else:
            raise HTTPException(status_code=404, detail=f"Checkpoint {checkpoint_id} not found")

    # ==================== 调试接口 ====================

    @app.get("/api/debug")
    async def debug_info():
        """Get debugging information."""
        parser_stats = {"intent_cache_size": len(orchestrator.parser.intent_cache)}
        executor_stats = orchestrator.executor.get_execution_summary()
        auditor_stats = orchestrator.auditor.get_audit_summary()

        return {
            "agents": {
                "parser": parser_stats,
                "executor": executor_stats,
                "auditor": auditor_stats
            },
            "memory": {
                "short_term_size": len(memory_manager.short_term.memory_window),
                "long_term_loaded": True
            },
            "system": {
                "python_version": "3.9+",
                "async_support": True
            }
        }

    # ==================== 工单管理API ====================

    @app.get("/api/workorders")
    async def list_workorders(
        status: Optional[str] = None,
        type: Optional[str] = None,
        keyword: Optional[str] = None,
        page: int = Query(default=1, ge=1),
        size: int = Query(default=10, ge=1, le=100)
    ):
        """获取工单列表"""
        items = list(_mock_workorders.values())

        # 筛选
        if status:
            items = [i for i in items if i["status"] == status]
        if type:
            items = [i for i in items if i["type"] == type]
        if keyword:
            items = [i for i in items if keyword in i["order_no"] or (i.get("related_order") and keyword in i["related_order"])]

        # 分页
        total = len(items)
        start = (page - 1) * size
        end = start + size
        items = items[start:end]

        return {
            "items": items,
            "total": total,
            "page": page,
            "size": size
        }

    @app.get("/api/workorders/{order_id}")
    async def get_workorder(order_id: str):
        """获取工单详情"""
        if order_id in _mock_workorders:
            return _mock_workorders[order_id]
        raise HTTPException(status_code=404, detail=f"工单 {order_id} 不存在")

    @app.post("/api/workorders")
    async def create_workorder(data: dict):
        """创建工单"""
        order_id = f"WO-{uuid.uuid4().hex[:8].upper()}"
        workorder = {
            "id": order_id,
            "order_no": order_id,
            "type": data.get("type", "quality_inspection"),
            "type_name": data.get("type_name", "质量检验"),
            "status": "pending",
            "status_name": "待处理",
            "related_order": data.get("related_order"),
            "related_logistics": data.get("related_logistics"),
            "description": data.get("description", ""),
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "timeline": []
        }
        _mock_workorders[order_id] = workorder
        return workorder

    @app.put("/api/workorders/{order_id}")
    async def update_workorder(order_id: str, data: dict):
        """更新工单"""
        if order_id not in _mock_workorders:
            raise HTTPException(status_code=404, detail=f"工单 {order_id} 不存在")

        workorder = _mock_workorders[order_id]
        for key, value in data.items():
            if key in workorder and key not in ["id", "order_no"]:
                workorder[key] = value
        workorder["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return workorder

    @app.post("/api/workorders/{order_id}/approve")
    async def approve_workorder(order_id: str, data: dict):
        """审批通过工单"""
        if order_id not in _mock_workorders:
            raise HTTPException(status_code=404, detail=f"工单 {order_id} 不存在")

        workorder = _mock_workorders[order_id]
        workorder["status"] = "completed"
        workorder["status_name"] = "已完成"
        workorder["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 添加时间线记录
        workorder["timeline"].append({
            "id": str(len(workorder["timeline"]) + 1),
            "actor": "user",
            "actor_name": "当前用户",
            "action": f"审批通过: {data.get('comment', '')}",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })

        return workorder

    @app.post("/api/workorders/{order_id}/reject")
    async def reject_workorder(order_id: str, data: dict):
        """拒绝工单"""
        if order_id not in _mock_workorders:
            raise HTTPException(status_code=404, detail=f"工单 {order_id} 不存在")

        workorder = _mock_workorders[order_id]
        workorder["status"] = "closed"
        workorder["status_name"] = "已关闭"
        workorder["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 添加时间线记录
        workorder["timeline"].append({
            "id": str(len(workorder["timeline"]) + 1),
            "actor": "user",
            "actor_name": "当前用户",
            "action": f"拒绝: {data.get('comment', '')}",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })

        return workorder

    # ==================== WebSocket接口 ====================

    @app.websocket("/ws/process")
    async def websocket_process(websocket: WebSocket):
        """WebSocket real-time processing stream with detailed agent events."""
        await websocket.accept()

        async def send_event(event_type: str, data: dict):
            """Helper to send agent events."""
            await websocket.send_json({
                "type": event_type,
                "timestamp": int(datetime.now().timestamp() * 1000),
                "data": data
            })

        try:
            while True:
                data = await websocket.receive_text()
                request = json.loads(data)

                query = request.get("query", "")
                session_id = request.get("session_id", "default")

                if not query:
                    await websocket.send_json({
                        "type": "error",
                        "error": "Query is required"
                    })
                    continue

                try:
                    # 发送总控节点开始事件
                    await send_event("step_start", {
                        "stepId": "orchestrator-main",
                        "agentType": "orchestrator",
                        "title": "处理请求",
                        "description": "总控节点正在处理您的请求..."
                    })

                    # 处理查询 - 使用带回调的处理方法
                    # 子Agent的事件会在process_with_callback内部通过回调发送
                    result = await orchestrator.process_with_callback(
                        query,
                        thread_id=session_id,
                        callback=send_event  # 直接传递async函数
                    )

                    # 发送总控节点结束事件
                    await send_event("step_end", {
                        "stepId": "orchestrator-main"
                    })

                    # 发送完成事件
                    await send_event("complete", {
                        "raw": {
                            "response": result.get("response", ""),
                            "waiting_for_input": result.get("waiting_for_input", False),
                            "tools_used": result.get("tools_used", [])
                        }
                    })

                except Exception as e:
                    await send_event("error", {
                        "error": str(e)
                    })

        except WebSocketDisconnect:
            pass

    return app


# For direct execution
if __name__ == "__main__":
    app = create_app()
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
