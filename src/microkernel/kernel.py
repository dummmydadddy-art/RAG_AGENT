from typing import Any, Dict, List, Type
from src.microkernel.registry import PluginRegistry
from src.microkernel.lifecycle import PluginLifecycle


class Kernel:
    """
    Extensible microkernel orchestrating plugin dependency ordering, lifecycles, and event broadcasting.
    """

    def __init__(self) -> None:
        self.registry = PluginRegistry()
        self.lifecycles: Dict[str, PluginLifecycle] = {}
        self.instances: Dict[str, Any] = {}
        self._booted = False

    def register_plugin(self, plugin_cls: Type) -> None:
        self.registry.register(plugin_cls)

    def boot(self) -> None:
        order = self.registry.resolve_boot_order()
        for name in order:
            cls = self.registry.plugins[name]
            inst = cls()
            lc = PluginLifecycle(name, inst)
            lc.boot()
            self.lifecycles[name] = lc
            self.instances[name] = inst
        self._booted = True

    def dispatch_event(self, event_name: str, payload: Any) -> List[Any]:
        if not self._booted:
            raise RuntimeError("Kernel must be booted before dispatching events")

        responses: List[Any] = []
        for name, inst in self.instances.items():
            if hasattr(inst, "on_event"):
                res = inst.on_event(event_name, payload)
                if res is not None:
                    responses.append(res)
        return responses

    def shutdown(self) -> None:
        for lc in reversed(list(self.lifecycles.values())):
            lc.stop()
        self._booted = False
