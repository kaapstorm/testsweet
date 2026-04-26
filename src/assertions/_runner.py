from types import ModuleType
from typing import Callable

from assertions._discover import discover
from assertions._test_class import Test, _public_methods


def run(
    module: ModuleType,
) -> list[tuple[Callable, Exception | None]]:
    results: list[tuple[Callable, Exception | None]] = []
    for unit in discover(module):
        if isinstance(unit, type) and issubclass(unit, Test):
            instance = unit()
            with instance:
                for name in _public_methods(unit):
                    bound = getattr(instance, name)
                    try:
                        bound()
                    except Exception as exc:
                        results.append((bound, exc))
                    else:
                        results.append((bound, None))
        else:
            try:
                unit()
            except Exception as exc:
                results.append((unit, exc))
            else:
                results.append((unit, None))
    return results
