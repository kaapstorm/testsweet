from types import ModuleType
from typing import Callable

from assertions._discover import discover


def run(
    module: ModuleType,
) -> list[tuple[Callable, Exception | None]]:
    results: list[tuple[Callable, Exception | None]] = []
    for func in discover(module):
        try:
            func()
        except Exception as exc:
            results.append((func, exc))
        else:
            results.append((func, None))
    return results
