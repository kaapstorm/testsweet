"""The ``@xfail`` decorator and its marker dataclass."""
from dataclasses import dataclass

from testsweet._markers import XFAIL_MARKER


@dataclass(frozen=True)
class XFailMarker:
    """Frozen marker attached to a test by ``@xfail``."""

    reason: str | None
    condition: bool


def xfail(*args, reason=None, if_=True):
    """Mark a test as expected to fail.

    Usable bare (``@xfail``) or called (``@xfail(reason='...')``,
    ``@xfail(if_=expr)``). When ``if_`` is False the marker is still
    attached but with ``condition=False`` so the runner ignores it.

    A test that unexpectedly passes is recorded as ``XPassed``, which
    is treated as a failure: either the underlying bug is fixed
    (remove the marker) or the test was wrongly marked.
    """
    if (
        len(args) == 1
        and callable(args[0])
        and reason is None
        and if_ is True
    ):
        # Bare @xfail.
        setattr(
            args[0],
            XFAIL_MARKER,
            XFailMarker(reason=None, condition=True),
        )
        return args[0]
    if args:
        raise TypeError('xfail() takes only keyword arguments')

    marker = XFailMarker(reason=reason, condition=bool(if_))

    def decorator(func):
        setattr(func, XFAIL_MARKER, marker)
        return func

    return decorator
