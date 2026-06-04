"""
Configuration and environment settings for Supply Chain Agent.

Settings can be loaded from:
1. Environment variables (with SCA_ prefix)
2. .env file
3. Database (agent_config table loaded from dataset/OtherData/config.yaml)

M35修复：明确配置加载优先级
==============================
配置加载优先级（从高到低）：
1. 环境变量（SCA_* 前缀）- 最高优先级，用于生产环境覆盖
2. .env 文件 - 本地开发配置
3. 数据库配置（agent_config表）- 默认值，可被上述覆盖
4. 代码默认值 - 最低优先级

注意：数据库配置通过 load_from_database() 加载，会覆盖代码默认值，
但会被环境变量和 .env 文件覆盖。
"""

import os
from typing import Optional, Dict, Any

from pydantic_settings import BaseSettings


# 配置加载优先级常量
CONFIG_PRIORITY = {
    "env_var": 1,      # 最高优先级
    "env_file": 2,     # 次高优先级
    "database": 3,     # 数据库配置
    "default": 4       # 代码默认值
}


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

    # Skill 配置
    use_skill_for_approval: bool = True  # 启用 skill 模式处理审批工单
    skill_fallback_to_prompt: bool = True  # skill 加载失败时降级到 prompt


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

    # L6修复：魔法数字常量化
    # 记忆重要性默认值
    default_importance: float = 0.7
    importance_high: float = 0.9
    importance_medium: float = 0.6
    importance_low: float = 0.4

    # 重试和循环限制
    max_clarification_loops: int = 3
    max_error_count: int = 3
    max_resume_attempts: int = 5

    # 历史和缓存限制
    max_context_window: int = 20
    max_execution_history: int = 100
    max_intent_cache_size: int = 100

    # 置信度阈值
    confidence_high: float = 0.9
    confidence_medium: float = 0.7
    confidence_low: float = 0.5
    confidence_threshold: float = 0.4

    # 分页默认值
    default_page_limit: int = 20
    max_page_limit: int = 100

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

            # M35修复：记录配置加载来源
            if loaded:
                print(f"[Config] 从数据库加载配置: {list(loaded.keys())}")

            return loaded
        except Exception as e:
            print(f"Warning: Could not load config from database: {e}")
            return {}


# Load settings (M35修复：记录配置加载来源)
settings = Settings()

# 检查环境变量覆盖
_env_overrides = []
if settings.llm_api_key:
    _env_overrides.append("llm_api_key")
if settings.anthropic_api_key:
    _env_overrides.append("anthropic_api_key")

# Try to load from database on import
try:
    _db_loaded = settings.load_from_database()
    if _env_overrides:
        print(f"[Config] 环境变量覆盖: {_env_overrides}")
except Exception as e:
    print(f"[Config] 数据库配置加载跳过: {e}")