"""The ``@skip`` decorator and its marker dataclass."""
from dataclasses import dataclass

from testsweet._condition_decorator import (
    Condition,
    make_condition_decorator,
)
from testsweet._markers import SKIP_MARKER


@dataclass(frozen=True)
class SkipMarker:
    """Frozen marker attached to a test by ``@skip``.

    ``condition`` may be a bool or a zero-arg callable returning a
    bool. The runner resolves a callable at run time, so conditions
    can reference state that is not available at import time.
    """

    reason: str | None
    condition: Condition


skip = make_condition_decorator('skip', SkipMarker, SKIP_MARKER)
"""Mark a test as skipped.

Usable bare (``@skip``) or called: ``@skip(reason='…')``,
``@skip(condition=expr)``, or both. ``condition`` may be a bool or a
zero-arg callable; a callable is resolved at run time, so passing a
function reference (``@skip(condition=is_windows)``) does what you'd
expect rather than silently being truthy.

Skip wins over ``@xfail`` when both decorators are applied.
"""
