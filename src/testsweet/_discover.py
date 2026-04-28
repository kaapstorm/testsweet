from types import ModuleType
from typing import Callable

from testsweet._markers import TEST_MARKER


def discover(module: ModuleType) -> list[Callable]:
    return [
        value
        for value in vars(module).values()
        if callable(value) and getattr(value, TEST_MARKER, False) is True
    ]
