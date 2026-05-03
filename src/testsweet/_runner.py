"""Run resolved test units and collect results."""
from contextlib import AbstractContextManager, nullcontext
from types import ModuleType
from typing import Any, Callable

from testsweet._resolve import resolve_units


def run(
    module: ModuleType,
    names: list[str] | None = None,
    wrap_unit: Callable[[str], AbstractContextManager[Any]] | None = None,
) -> list[tuple[str, Exception | None]]:
    """Run the tests in ``module``.

    If ``names`` is given, only run tests whose qualified names appear
    in the list. If ``wrap_unit`` is given, each test call is wrapped
    in ``wrap_unit(name)``, which must return a context manager.

    Returns a list of ``(name, exception_or_none)`` tuples — ``None``
    indicates success.
    """
    if wrap_unit is None:
        wrap_unit = lambda _name: nullcontext()
    results: list[tuple[str, Exception | None]] = []
    for name, call in resolve_units(module, names):
        try:
            with wrap_unit(name):
                call()
        except Exception as exc:
            results.append((name, exc))
        else:
            results.append((name, None))
    return results
