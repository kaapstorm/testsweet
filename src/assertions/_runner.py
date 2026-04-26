from types import ModuleType
from typing import Callable

from assertions._discover import discover
from assertions._test_class import Test, _public_methods


def run(
    module: ModuleType,
) -> list[tuple[str, Exception | None]]:
    results: list[tuple[str, Exception | None]] = []
    for unit in discover(module):
        if isinstance(unit, type) and issubclass(unit, Test):
            instance = unit()
            with instance:
                for name in _public_methods(unit):
                    bound = getattr(instance, name)
                    _invoke(bound, bound.__qualname__, results)
        else:
            _invoke(unit, unit.__qualname__, results)
    return results


def _invoke(
    func: Callable,
    qualname: str,
    results: list[tuple[str, Exception | None]],
) -> None:
    try:
        func()
    except Exception as exc:
        results.append((qualname, exc))
    else:
        results.append((qualname, None))
