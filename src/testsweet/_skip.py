"""The ``@skip`` decorator and its marker dataclass."""
from dataclasses import dataclass

from testsweet._markers import SKIP_MARKER


@dataclass(frozen=True)
class SkipMarker:
    """Frozen marker attached to a test by ``@skip``."""

    reason: str | None
    condition: bool


def skip(*args, reason=None, if_=True):
    """Mark a test as skipped.

    Usable bare (``@skip``) or called (``@skip(reason='...')``,
    ``@skip(if_=expr)``). When ``if_`` is False, the marker is still
    attached but with ``condition=False`` so the runner ignores it
    (introspection can still see the marker).
    """
    if (
        len(args) == 1
        and callable(args[0])
        and reason is None
        and if_ is True
    ):
        # Bare @skip — args[0] is the function being decorated.
        setattr(
            args[0],
            SKIP_MARKER,
            SkipMarker(reason=None, condition=True),
        )
        return args[0]
    if args:
        raise TypeError('skip() takes only keyword arguments')

    marker = SkipMarker(reason=reason, condition=bool(if_))

    def decorator(func):
        setattr(func, SKIP_MARKER, marker)
        return func

    return decorator
