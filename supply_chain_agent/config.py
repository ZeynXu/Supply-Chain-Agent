"""
Configuration and environment settings for Supply Chain Agent.

Settings can be loaded from:
1. Environment variables (with SCA_ prefix)
2. .env file
3. Database (agent_config table loaded from dataset/OtherData/config.yaml)
"""

import os
from typing import Optional, Dict, Any

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    # Anthropic API
    anthropic_api_key: Optional[str] = None

    # LLM配置
    # 使用智谱AI GLM-4.7模型
    llm_provider: str = "zhipu"  # zhipu / openai
    llm_model: str = "glm-4.7"
    llm_api_key: str = ""  # 从 .env 文件加载 SCA_LLM_API_KEY
    llm_base_url: str = "https://open.bigmodel.cn/api/paas/v4"
    llm_temperature: float = 0.7
    llm_max_tokens: int = 65536


    # 意图识别配置
    intent_rule_first: bool = True  # 优先使用规则快速路径
    intent_confidence_threshold: float = 0.75  # 低于此阈值调用LLM

    # 降级策略配置
    fallback_strategy: str = "knowledge_first"  # knowledge_first / llm_only

    # Agent configuration
    agent_model: str = "MiniMax-M2.5"
    agent_temperature: float = 0.1
    max_retries: int = 3
    clarification_max_attempts: int = 3

    # Memory configuration
    memory_window_size: int = 20
    vector_store_path: str = "./supply_chain_agent/data/vector_store"
    sqlite_db_path: str = "./supply_chain_agent/data/agent_memory.db"

    # MCP tools configuration
    mcp_server_host: str = "localhost"
    mcp_server_port: int = 8001
    circuit_breaker_failures: int = 5
    circuit_breaker_reset_timeout: int = 300  # 5 minutes

    # Tool call configuration (from config.yaml)
    tool_call_timeout: int = 10  # seconds

    # Short-term memory configuration (from config.yaml)
    short_term_max_tokens: int = 4096
    summary_trigger_tokens: int = 3000

    # Degradation configuration (from config.yaml)
    static_response_enabled: bool = True
    cache_fallback_enabled: bool = True

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

    def load_from_database(self) -> Dict[str, Any]:
        """
        Load configuration from database.

        Returns:
            Dict of loaded config values
        """
        try:
            from supply_chain_agent.data.supply_chain_db import get_all_config
            db_config = get_all_config()

            loaded = {}
            # Map database config to settings
            if "intent_classifier" in db_config:
                ic = db_config["intent_classifier"]
                if "threshold" in ic:
                    self.intent_confidence_threshold = float(ic["threshold"])
                    loaded["intent_confidence_threshold"] = ic["threshold"]

            if "execution" in db_config:
                exec_cfg = db_config["execution"]
                if "max_retries" in exec_cfg:
                    self.max_retries = int(exec_cfg["max_retries"])
                    loaded["max_retries"] = exec_cfg["max_retries"]
                if "tool_call_timeout" in exec_cfg:
                    self.tool_call_timeout = int(exec_cfg["tool_call_timeout"])
                    loaded["tool_call_timeout"] = exec_cfg["tool_call_timeout"]
                if "circuit_breaker" in exec_cfg:
                    cb = exec_cfg["circuit_breaker"]
                    if "failure_threshold" in cb:
                        self.circuit_breaker_failures = int(cb["failure_threshold"])
                        loaded["circuit_breaker_failures"] = cb["failure_threshold"]
                    if "recovery_timeout" in cb:
                        self.circuit_breaker_reset_timeout = int(cb["recovery_timeout"])
                        loaded["circuit_breaker_reset_timeout"] = cb["recovery_timeout"]

            if "clarification" in db_config:
                clar = db_config["clarification"]
                if "max_rounds" in clar:
                    self.clarification_max_attempts = int(clar["max_rounds"])
                    loaded["clarification_max_attempts"] = clar["max_rounds"]

            if "memory" in db_config:
                mem = db_config["memory"]
                if "short_term_max_tokens" in mem:
                    self.short_term_max_tokens = int(mem["short_term_max_tokens"])
                    loaded["short_term_max_tokens"] = mem["short_term_max_tokens"]
                if "summary_trigger_tokens" in mem:
                    self.summary_trigger_tokens = int(mem["summary_trigger_tokens"])
                    loaded["summary_trigger_tokens"] = mem["summary_trigger_tokens"]

            if "degradation" in db_config:
                deg = db_config["degradation"]
                if "static_response_enabled" in deg:
                    self.static_response_enabled = bool(deg["static_response_enabled"])
                    loaded["static_response_enabled"] = deg["static_response_enabled"]
                if "cache_fallback_enabled" in deg:
                    self.cache_fallback_enabled = bool(deg["cache_fallback_enabled"])
                    loaded["cache_fallback_enabled"] = deg["cache_fallback_enabled"]

            return loaded
        except Exception as e:
            print(f"Warning: Could not load config from database: {e}")
            return {}


# Load settings
settings = Settings()

# Try to load from database on import (silently)
try:
    settings.load_from_database()
except:
    pass  # Database may not be initialized yet