"""The ``@xfail`` decorator and its marker dataclass."""
from dataclasses import dataclass

from testsweet._condition_decorator import (
    Condition,
    make_condition_decorator,
)
from testsweet._markers import XFAIL_MARKER


@dataclass(frozen=True)
class XFailMarker:
    """Frozen marker attached to a test by ``@xfail``.

    ``condition`` may be a bool or a zero-arg callable returning a
    bool, resolved at run time.
    """

    reason: str | None
    condition: Condition


xfail = make_condition_decorator('xfail', XFailMarker, XFAIL_MARKER)
"""Mark a test as expected to fail.

Usable bare (``@xfail``) or called: ``@xfail(reason='…')``,
``@xfail(condition=expr)``, or both. ``condition`` may be a bool or a
zero-arg callable.

A test that unexpectedly passes is recorded as ``XPassed``, which is
treated as a failure: either the underlying bug is fixed (remove the
marker) or the test was wrongly marked.
"""
