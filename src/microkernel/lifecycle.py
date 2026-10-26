from enum import Enum
from typing import Any, Dict


class LifecycleState(str, Enum):
    REGISTERED = "REGISTERED"
    INITIALIZED = "INITIALIZED"
    ACTIVE = "ACTIVE"
    STOPPED = "STOPPED"


class PluginLifecycle:
    """
    Manages state transitions of plugin instances.
    """

    def __init__(self, name: str, instance: Any) -> None:
        self.name = name
        self.instance = instance
        self.state = LifecycleState.REGISTERED

    def boot(self) -> None:
        if hasattr(self.instance, "on_boot"):
            self.instance.on_boot()
        self.state = LifecycleState.ACTIVE

    def stop(self) -> None:
        if hasattr(self.instance, "on_stop"):
            self.instance.on_stop()
        self.state = LifecycleState.STOPPED
