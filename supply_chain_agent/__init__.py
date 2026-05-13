"""
Supply Chain Agent System
=========================

An intelligent multi-agent system for supply chain work order processing.

This system implements a L3-level autonomous agent with a star topology architecture:
- Orchestrator Agent (总控)
- Parser Agent (解析师)
- Executor Agent (调度员)
- Auditor Agent (审计员)

Key Features:
- Three-level intent classification system
- Multi-round information collection with clarification strategies
- Cross-system query with MCP tools and fallback mechanisms
- Multi-modal report generation
- Circuit breaker pattern for error handling
- Three-layer memory system (short-term, working, long-term)
- LangGraph-based workflow orchestration
- MCP tool integration for enterprise system simulation
"""

__version__ = "1.0.0"
__author__ = "Supply Chain Agent Team"
__license__ = "MIT"