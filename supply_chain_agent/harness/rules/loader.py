"""
业务规则 YAML 加载器

支持热加载，监听文件变更自动重载规则。
"""

import yaml
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
import threading
import time
import os
import logging

logger = logging.getLogger(__name__)

# 可选依赖：watchdog 用于文件监听
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    Observer = None
    FileSystemEventHandler = None


@dataclass
class BusinessRule:
    """业务规则定义"""

    id: str
    name: str
    condition: str
    action: str
    message: str
    enabled: bool = True
    severity: str = "warn"  # warn, block
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BusinessRule':
        """从字典创建规则对象"""
        return cls(
            id=data['id'],
            name=data.get('name', data['id']),
            condition=data['condition'],
            action=data['action'],
            message=data.get('message', ''),
            enabled=data.get('enabled', True),
            severity=data.get('severity', 'warn'),
            metadata=data.get('metadata', {}),
        )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'id': self.id,
            'name': self.name,
            'condition': self.condition,
            'action': self.action,
            'message': self.message,
            'enabled': self.enabled,
            'severity': self.severity,
            'metadata': self.metadata,
        }


class RuleLoader:
    """
    业务规则加载器

    支持从 YAML 文件加载规则，支持热重载。
    """

    DEFAULT_RULES_PATH = Path(__file__).parent / "business_rules.yaml"

    def __init__(
        self,
        rules_path: Optional[str] = None,
        auto_reload: bool = False,
        reload_interval: float = 5.0,
    ):
        """
        初始化规则加载器

        Args:
            rules_path: 规则文件路径，默认使用内置的 business_rules.yaml
            auto_reload: 是否启用自动重载（需要 watchdog）
            reload_interval: 自动重载检查间隔（秒）
        """
        self.rules_path = Path(rules_path) if rules_path else self.DEFAULT_RULES_PATH
        self.auto_reload = auto_reload
        self.reload_interval = reload_interval

        self._rules: Dict[str, BusinessRule] = {}
        self._lock = threading.RLock()
        self._observer: Optional[Any] = None
        self._last_modified: float = 0

        # 初始加载
        self._load_rules()

        # 启动自动重载
        if auto_reload and WATCHDOG_AVAILABLE:
            self._start_observer()
        elif auto_reload and not WATCHDOG_AVAILABLE:
            logger.warning("watchdog not installed, auto_reload disabled")

    def _load_rules(self) -> None:
        """从 YAML 文件加载规则"""
        if not self.rules_path.exists():
            raise FileNotFoundError(f"Rules file not found: {self.rules_path}")

        with open(self.rules_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        if not data or 'rules' not in data:
            logger.warning(f"No rules found in {self.rules_path}")
            return

        with self._lock:
            self._rules.clear()
            for rule_data in data['rules']:
                try:
                    rule = BusinessRule.from_dict(rule_data)
                    self._rules[rule.id] = rule
                except KeyError as e:
                    logger.error(f"Invalid rule definition, missing key: {e}")
                    continue

        self._last_modified = self.rules_path.stat().st_mtime
        logger.info(f"Loaded {len(self._rules)} rules from {self.rules_path}")

    def _start_observer(self) -> None:
        """启动文件监听器"""

        class Handler(FileSystemEventHandler):
            def __init__(self, loader: 'RuleLoader'):
                self.loader = loader

            def on_modified(self, event):
                if not event.is_directory and Path(event.src_path) == self.loader.rules_path:
                    logger.info(f"Rules file modified, reloading: {event.src_path}")
                    self.loader._load_rules()

        if Observer is not None:
            self._observer = Observer()
            handler = Handler(self)
            self._observer.schedule(handler, str(self.rules_path.parent), recursive=False)
            self._observer.start()
            logger.info(f"Started file observer for {self.rules_path}")

    def stop_observer(self) -> None:
        """停止文件监听器"""
        if self._observer:
            self._observer.stop()
            self._observer.join()
            self._observer = None

    def reload_rules(self) -> bool:
        """
        手动重载规则

        Returns:
            是否成功重载
        """
        try:
            self._load_rules()
            return True
        except Exception as e:
            logger.error(f"Failed to reload rules: {e}")
            return False

    def get_rule(self, rule_id: str) -> Optional[BusinessRule]:
        """获取指定规则"""
        with self._lock:
            return self._rules.get(rule_id)

    def get_all_rules(self, enabled_only: bool = True) -> List[BusinessRule]:
        """
        获取所有规则

        Args:
            enabled_only: 是否只返回启用的规则

        Returns:
            规则列表
        """
        with self._lock:
            rules = list(self._rules.values())
            if enabled_only:
                rules = [r for r in rules if r.enabled]
            return rules

    def get_rules_by_severity(self, severity: str) -> List[BusinessRule]:
        """获取指定严重级别的规则"""
        with self._lock:
            return [r for r in self._rules.values() if r.severity == severity and r.enabled]

    def add_rule(self, rule: BusinessRule) -> None:
        """添加规则（运行时）"""
        with self._lock:
            self._rules[rule.id] = rule

    def remove_rule(self, rule_id: str) -> bool:
        """移除规则（运行时）"""
        with self._lock:
            if rule_id in self._rules:
                del self._rules[rule_id]
                return True
            return False

    def __len__(self) -> int:
        return len(self._rules)

    def __contains__(self, rule_id: str) -> bool:
        return rule_id in self._rules

    def __del__(self):
        self.stop_observer()
