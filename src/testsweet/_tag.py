"""The ``@tag`` decorator for labelling tests."""
from testsweet._markers import TAGS_MARKER


def tag(*names):
    """Attach string tags to a test.

    Stack ``@tag`` calls or pass multiple names in one call; the
    accumulated set is stored as a frozenset under ``TAGS_MARKER``.
    Tags are stored but not yet used by the runner in 0.2.0 —
    groundwork for future filtering.
    """
    if not names:
        raise TypeError('tag() requires at least one tag name')
    if not all(isinstance(n, str) for n in names):
        raise TypeError('tag names must be strings')
    new = frozenset(names)

    def decorator(func):
        existing: frozenset[str] = getattr(func, TAGS_MARKER, frozenset())
        setattr(func, TAGS_MARKER, existing | new)
        return func

    return decorator
