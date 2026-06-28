"""Run resolved test units and collect results."""
import io
from contextlib import (
    AbstractContextManager,
    nullcontext,
    redirect_stderr,
    redirect_stdout,
)
from types import ModuleType
from typing import Any, Callable

from testsweet._condition_decorator import active_marker
from testsweet._markers import SKIP_MARKER, XFAIL_MARKER
from testsweet._outcomes import (
    Errored,
    Failed,
    Outcome,
    Passed,
    Result,
    Skipped,
    XFailed,
    XPassed,
)
from testsweet._resolve import TagFilter, resolve_units
from testsweet._skip import SkipMarker
from testsweet._xfail import XFailMarker


def run(
    module: ModuleType,
    names: list[str] | None = None,
    wrap_unit: Callable[[str], AbstractContextManager[Any]] | None = None,
    keep: TagFilter | None = None,
) -> list[Result]:
    """Run the tests in ``module``.

    If ``names`` is given, only run tests whose qualified names appear
    in the list. If ``wrap_unit`` is given, each test call is wrapped
    in ``wrap_unit(name)``, which must return a context manager. If
    ``keep`` is given, each test's effective tag set is passed to it
    and the test runs only when the predicate returns truthy. A
    method's effective tag set is the union of its class's tags and
    its own.

    Returns a list of ``Result`` records. Each carries the unit's
    ``name``, its ``outcome`` (one of ``Passed``, ``Failed``,
    ``Errored``, ``Skipped``, ``XFailed``, ``XPassed``), and the
    ``stdout``/``stderr`` it printed (empty unless it wrote to those
    streams; captured only while the unit body runs).
    """
    if wrap_unit is None:
        def wrap_unit(_name: str) -> AbstractContextManager[Any]:
            return nullcontext()
    results: list[Result] = []
    for name, call in resolve_units(module, names, keep=keep):
        results.append(_run_one(name, call, wrap_unit))
    return results


def _run_one(
    name: str,
    call: Callable[[], Any],
    wrap_unit: Callable[[str], AbstractContextManager[Any]],
) -> Result:
    try:
        skip_marker: SkipMarker | None = active_marker(call, SKIP_MARKER)
    except Exception as exc:
        return Result(name, Errored(exc))
    if skip_marker is not None:
        return Result(name, Skipped(skip_marker.reason))
    try:
        xfail_marker: XFailMarker | None = active_marker(call, XFAIL_MARKER)
    except Exception as exc:
        return Result(name, Errored(exc))
    out_buf = io.StringIO()
    err_buf = io.StringIO()
    if xfail_marker is not None:
        try:
            with (
                wrap_unit(name),
                redirect_stdout(out_buf),
                redirect_stderr(err_buf),
            ):
                call()
        except Exception as exc:
            outcome: Outcome = XFailed(exc, xfail_marker.reason)
        else:
            outcome = XPassed(xfail_marker.reason)
        return Result(name, outcome, out_buf.getvalue(), err_buf.getvalue())
    try:
        with (
            wrap_unit(name),
            redirect_stdout(out_buf),
            redirect_stderr(err_buf),
        ):
            call()
    except AssertionError as exc:
        outcome = Failed(exc)
    except Exception as exc:
        outcome = Errored(exc)
    else:
        outcome = Passed()
    return Result(name, outcome, out_buf.getvalue(), err_buf.getvalue())
