"""Run resolved test units and collect results."""
from contextlib import AbstractContextManager, nullcontext
from types import ModuleType
from typing import Any, Callable

from testsweet._condition_decorator import active_marker
from testsweet._markers import SKIP_MARKER, XFAIL_MARKER
from testsweet._outcomes import (
    Errored,
    Failed,
    Outcome,
    Passed,
    Skipped,
    XFailed,
    XPassed,
)
from testsweet._resolve import resolve_units
from testsweet._skip import SkipMarker
from testsweet._xfail import XFailMarker


def run(
    module: ModuleType,
    names: list[str] | None = None,
    wrap_unit: Callable[[str], AbstractContextManager[Any]] | None = None,
) -> list[tuple[str, Outcome]]:
    """Run the tests in ``module``.

    If ``names`` is given, only run tests whose qualified names appear
    in the list. If ``wrap_unit`` is given, each test call is wrapped
    in ``wrap_unit(name)``, which must return a context manager.

    Returns a list of ``(name, outcome)`` tuples. ``outcome`` is one
    of ``Passed``, ``Failed``, ``Errored``, ``Skipped``, ``XFailed``,
    ``XPassed``.
    """
    if wrap_unit is None:
        def wrap_unit(_name: str) -> AbstractContextManager[Any]:
            return nullcontext()
    results: list[tuple[str, Outcome]] = []
    for name, call in resolve_units(module, names):
        results.append((name, _run_one(name, call, wrap_unit)))
    return results


def _run_one(
    name: str,
    call: Callable[[], Any],
    wrap_unit: Callable[[str], AbstractContextManager[Any]],
) -> Outcome:
    try:
        skip_marker: SkipMarker | None = active_marker(call, SKIP_MARKER)
    except Exception as exc:
        return Errored(exc)
    if skip_marker is not None:
        return Skipped(skip_marker.reason)
    try:
        xfail_marker: XFailMarker | None = active_marker(call, XFAIL_MARKER)
    except Exception as exc:
        return Errored(exc)
    if xfail_marker is not None:
        try:
            with wrap_unit(name):
                call()
        except Exception as exc:
            return XFailed(exc, xfail_marker.reason)
        return XPassed(xfail_marker.reason)
    try:
        with wrap_unit(name):
            call()
    except AssertionError as exc:
        return Failed(exc)
    except Exception as exc:
        return Errored(exc)
    return Passed()
