"""Hybrid agent architecture for NEO.

Use lazy imports to avoid triggering the full module chain (litellm, etc.)
on every import from hybrid.*.
"""

from hybrid.registry import ToolRegistry

__all__ = [
    "ToolRegistry",
    "get_orchestrator",
    "init_hybrid_system",
    "register_all_tools",
]


def __getattr__(name: str):
    if name == "get_orchestrator":
        from hybrid.bootstrap import get_orchestrator as _fn
        return _fn
    if name == "init_hybrid_system":
        from hybrid.bootstrap import init_hybrid_system as _fn
        return _fn
    if name == "register_all_tools":
        from hybrid.bootstrap import register_all_tools as _fn
        return _fn
    raise AttributeError(f"module 'hybrid' has no attribute '{name}'")
