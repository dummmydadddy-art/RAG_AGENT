# Task Specification: Pluggable Microkernel Architecture with Sandboxing

## 1. Multi-Module Architecture
Implement modules in `src/microkernel/`:
- `registry.py`: `PluginRegistry` tracking plugin metadata and dependencies.
- `lifecycle.py`: `PluginLifecycle` managing state (`REGISTERED`, `INITIALIZED`, `ACTIVE`, `STOPPED`).
- `kernel.py`: `Kernel` coordinating lifecycle, dependency ordering, and event dispatch.

### Kernel Contract
```python
class Kernel:
    def __init__(self) -> None:
    def register_plugin(self, plugin_cls: type) -> None:
    def boot(self) -> None:
    def dispatch_event(self, event_name: str, payload: Any) -> List[Any]:
    def shutdown(self) -> None:
```
