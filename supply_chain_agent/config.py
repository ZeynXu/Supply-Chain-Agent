"""
Configuration and environment settings for Supply Chain Agent.
"""

import os
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    # Anthropic API
    anthropic_api_key: Optional[str] = None

    # LLM配置（新增）
    # 使用智谱AI GLM-4.7模型
    llm_provider: str = "zhipu"  # zhipu / openai
    llm_model: str = "glm-4.7"
    llm_api_key: str = your_api_key
    llm_base_url: str = "https://open.bigmodel.cn/api/paas/v4"
    llm_temperature: float = 0.7
    llm_max_tokens: int = 65536


    # 意图识别配置（新增）
    intent_rule_first: bool = True  # 优先使用规则快速路径
    intent_confidence_threshold: float = 0.7  # 低于此阈值调用LLM

    # 降级策略配置（新增）
    fallback_strategy: str = "knowledge_first"  # knowledge_first / llm_only

    # Agent configuration
    agent_model: str = "MiniMax-M2.5"
    agent_temperature: float = 0.1
    max_retries: int = 3
    clarification_max_attempts: int = 3

    # Memory configuration
    memory_window_size: int = 20
    vector_store_path: str = "./data/vector_store"
    sqlite_db_path: str = "./data/agent_memory.db"

    # MCP tools configuration
    mcp_server_host: str = "localhost"
    mcp_server_port: int = 8001
    circuit_breaker_failures: int = 3
    circuit_breaker_reset_timeout: int = 300  # 5 minutes

    # Web interface
    web_port: int = 8000
    debug_mode: bool = True

    # Frontend config (optional, for Vite)
    vite_api_base_url: Optional[str] = None
    vite_app_title: Optional[str] = None

    class Config:
        env_file = ".env"
        env_prefix = "SCA_"
        extra = "ignore"  # Ignore extra fields


# Load settings
settings = Settings()