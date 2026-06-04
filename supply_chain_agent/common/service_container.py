"""
H4修复：服务容器 - 统一管理全局单例

提供轻量级依赖注入功能，解决全局单例问题：
1. 统一管理所有单例实例
2. 支持测试时替换/mock
3. 支持重置所有单例
4. 保持向后兼容

使用方式：
    # 获取服务
    llm = ServiceContainer.get_llm_client()
    memory = ServiceContainer.get_memory_manager()

    # 测试时替换
    ServiceContainer.set_llm_client(mock_llm)

    # 重置所有单例
    ServiceContainer.reset_all()
"""

from typing import Any, Optional, Dict, TypeVar, Callable
from contextlib import contextmanager

T = TypeVar('T')


class ServiceContainer:
    """
    轻量级服务容器

    统一管理全局单例，支持测试时替换和重置。
    """

    # 服务实例缓存
    _services: Dict[str, Any] = {}

    # 服务工厂函数
    _factories: Dict[str, Callable[[], Any]] = {}

    # 是否已初始化
    _initialized: bool = False

    @classmethod
    def _ensure_factories(cls):
        """确保工厂函数已注册"""
        if cls._initialized:
            return

        # 注册各服务的工厂函数（延迟导入避免循环依赖）
        cls._factories = {
            'llm_client': lambda: cls._create_llm_client(),
            'tool_client': lambda: cls._create_tool_client(),
            'memory_manager': lambda: cls._create_memory_manager(),
            'state_manager': lambda: cls._create_state_manager(),
            'ner_instance': lambda: cls._create_ner_instance(),
            'workflow_instance': lambda: cls._create_workflow_instance(),
        }
        cls._initialized = True

    # ========== 工厂方法 ==========

    @staticmethod
    def _create_llm_client():
        """创建LLM客户端"""
        from supply_chain_agent.agents.llm_client import get_llm_client
        return get_llm_client()

    @staticmethod
    def _create_tool_client():
        """创建工具客户端"""
        from supply_chain_agent.tools.client import get_tool_client
        return get_tool_client()

    @staticmethod
    def _create_memory_manager():
        """创建内存管理器"""
        from supply_chain_agent.memory.vector_store import MemoryManager
        return MemoryManager()

    @staticmethod
    def _create_state_manager():
        """创建状态管理器"""
        from supply_chain_agent.graph.state import StateManager
        return StateManager()

    @staticmethod
    def _create_ner_instance():
        """创建NER模型"""
        from supply_chain_agent.nlp.bert_ner import get_ner_model
        return get_ner_model()

    @staticmethod
    def _create_workflow_instance():
        """创建工作流实例"""
        from supply_chain_agent.graph.workflow import SupplyChainWorkflow
        return SupplyChainWorkflow()

    # ========== 获取服务 ==========

    @classmethod
    def get_llm_client(cls):
        """获取LLM客户端"""
        cls._ensure_factories()
        if 'llm_client' not in cls._services:
            cls._services['llm_client'] = cls._factories['llm_client']()
        return cls._services['llm_client']

    @classmethod
    def get_tool_client(cls):
        """获取工具客户端"""
        cls._ensure_factories()
        if 'tool_client' not in cls._services:
            cls._services['tool_client'] = cls._factories['tool_client']()
        return cls._services['tool_client']

    @classmethod
    def get_memory_manager(cls):
        """获取内存管理器"""
        cls._ensure_factories()
        if 'memory_manager' not in cls._services:
            cls._services['memory_manager'] = cls._factories['memory_manager']()
        return cls._services['memory_manager']

    @classmethod
    def get_state_manager(cls):
        """获取状态管理器"""
        cls._ensure_factories()
        if 'state_manager' not in cls._services:
            cls._services['state_manager'] = cls._factories['state_manager']()
        return cls._services['state_manager']

    @classmethod
    def get_ner_instance(cls):
        """获取NER模型"""
        cls._ensure_factories()
        if 'ner_instance' not in cls._services:
            cls._services['ner_instance'] = cls._factories['ner_instance']()
        return cls._services['ner_instance']

    @classmethod
    def get_workflow_instance(cls):
        """获取工作流实例"""
        cls._ensure_factories()
        if 'workflow_instance' not in cls._services:
            cls._services['workflow_instance'] = cls._factories['workflow_instance']()
        return cls._services['workflow_instance']

    # ========== 设置服务（用于测试） ==========

    @classmethod
    def set_llm_client(cls, client):
        """设置LLM客户端（用于测试）"""
        cls._services['llm_client'] = client

    @classmethod
    def set_tool_client(cls, client):
        """设置工具客户端（用于测试）"""
        cls._services['tool_client'] = client

    @classmethod
    def set_memory_manager(cls, manager):
        """设置内存管理器（用于测试）"""
        cls._services['memory_manager'] = manager

    @classmethod
    def set_state_manager(cls, manager):
        """设置状态管理器（用于测试）"""
        cls._services['state_manager'] = manager

    @classmethod
    def set_ner_instance(cls, instance):
        """设置NER模型（用于测试）"""
        cls._services['ner_instance'] = instance

    @classmethod
    def set_workflow_instance(cls, workflow):
        """设置工作流实例（用于测试）"""
        cls._services['workflow_instance'] = workflow

    # ========== 重置服务 ==========

    @classmethod
    def reset_llm_client(cls):
        """重置LLM客户端"""
        cls._services.pop('llm_client', None)
        # 同时重置底层单例
        try:
            from supply_chain_agent.agents.llm_client import reset_llm_client
            reset_llm_client()
        except ImportError:
            pass

    @classmethod
    def reset_tool_client(cls):
        """重置工具客户端"""
        cls._services.pop('tool_client', None)
        try:
            from supply_chain_agent.tools.client import reset_tool_client
            reset_tool_client()
        except ImportError:
            pass

    @classmethod
    def reset_all(cls):
        """
        重置所有服务

        用于测试清理，确保每个测试用例独立运行。
        """
        cls._services.clear()
        cls._initialized = False

        # 重置底层单例
        try:
            from supply_chain_agent.agents.llm_client import reset_llm_client
            reset_llm_client()
        except ImportError:
            pass

        try:
            from supply_chain_agent.tools.client import reset_tool_client
            reset_tool_client()
        except ImportError:
            pass

        try:
            from supply_chain_agent.memory.vector_store import reset_memory_manager
            reset_memory_manager()
        except ImportError:
            pass

        try:
            from supply_chain_agent.graph.state import reset_state_manager
            reset_state_manager()
        except ImportError:
            pass

        try:
            from supply_chain_agent.nlp.bert_ner import reset_ner_model
            reset_ner_model()
        except ImportError:
            pass

        try:
            from supply_chain_agent.graph.workflow import reset_workflow
            reset_workflow()
        except ImportError:
            pass

    # ========== 上下文管理器（用于测试） ==========

    @classmethod
    @contextmanager
    def override(cls, service_name: str, mock_instance: Any):
        """
        临时替换服务（上下文管理器）

        Args:
            service_name: 服务名称
            mock_instance: mock实例

        Example:
            with ServiceContainer.override('llm_client', mock_llm):
                # 在此上下文中使用mock_llm
                result = some_function()
        """
        original = cls._services.get(service_name)
        cls._services[service_name] = mock_instance
        try:
            yield
        finally:
            if original is None:
                cls._services.pop(service_name, None)
            else:
                cls._services[service_name] = original

    # ========== 状态查询 ==========

    @classmethod
    def get_loaded_services(cls) -> Dict[str, bool]:
        """获取已加载的服务状态"""
        return {
            'llm_client': 'llm_client' in cls._services,
            'tool_client': 'tool_client' in cls._services,
            'memory_manager': 'memory_manager' in cls._services,
            'state_manager': 'state_manager' in cls._services,
            'ner_instance': 'ner_instance' in cls._services,
            'workflow_instance': 'workflow_instance' in cls._services,
        }

    @classmethod
    def is_service_loaded(cls, service_name: str) -> bool:
        """检查服务是否已加载"""
        return service_name in cls._services


# 便捷函数
def get_service(name: str) -> Any:
    """获取服务"""
    getter = getattr(ServiceContainer, f'get_{name}', None)
    if getter:
        return getter()
    raise ValueError(f"Unknown service: {name}")


def reset_services():
    """重置所有服务"""
    ServiceContainer.reset_all()


__all__ = [
    'ServiceContainer',
    'get_service',
    'reset_services',
]
