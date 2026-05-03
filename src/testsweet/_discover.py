"""Discover ``@test``-marked callables and classes in a module."""
from types import ModuleType
from typing import Callable

from testsweet._markers import TEST_MARKER


def discover(module: ModuleType) -> list[Callable]:
    """Return module-level callables marked as test units.

    Order follows ``vars(module)`` (definition order on CPython 3.7+).
    Useful when embedding testsweet in a custom runner.
    """
    return [
        value
        for value in vars(module).values()
        if callable(value) and getattr(value, TEST_MARKER, False) is True
    ]
