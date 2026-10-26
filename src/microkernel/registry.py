from typing import Any, Dict, List, Type


class PluginRegistry:
    """
    Tracks registered plugins and resolves topological initialization order based on declared dependencies.
    """

    def __init__(self) -> None:
        self.plugins: Dict[str, Type] = {}
        self.dependencies: Dict[str, List[str]] = {}

    def register(self, plugin_cls: Type) -> None:
        name = getattr(plugin_cls, "name", plugin_cls.__name__)
        deps = getattr(plugin_cls, "dependencies", [])
        self.plugins[name] = plugin_cls
        self.dependencies[name] = list(deps)

    def resolve_boot_order(self) -> List[str]:
        # Kahn's algorithm for topological sorting
        in_degree: Dict[str, int] = {name: 0 for name in self.plugins}
        adj: Dict[str, List[str]] = {name: [] for name in self.plugins}

        for name, deps in self.dependencies.items():
            for dep in deps:
                if dep in self.plugins:
                    adj[dep].append(name)
                    in_degree[name] += 1

        queue = [name for name, deg in in_degree.items() if deg == 0]
        order = []

        while queue:
            curr = queue.pop(0)
            order.append(curr)
            for neighbor in adj[curr]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(order) < len(self.plugins):
            raise ValueError("Circular dependency detected among plugins")

        return order
