"""Shared scaffolding for condition-gated marker decorators.

``@skip`` and ``@xfail`` are structurally identical: both attach a
frozen marker carrying a ``reason`` and a ``condition`` (a bool or
zero-arg callable) and both support a bare and a called form. This
module factors out the construction so the two decorators stay in
lockstep.
"""
from typing import Callable, Union


Condition = Union[bool, Callable[[], bool]]


def make_condition_decorator(decorator_name, marker_cls, attr):
    """Build a decorator that attaches ``marker_cls(reason, condition)`` under ``attr``.

    The returned decorator supports the bare form (``@dec``) and the
    called form (``@dec(reason='…')``, ``@dec(condition=expr)``,
    ``@dec(reason='…', condition=expr)``). ``condition`` is stored
    as-is — the runner resolves a callable lazily at run time.
    """
    def decorator(*args, reason=None, condition=True):
        if (
            len(args) == 1
            and callable(args[0])
            and reason is None
            and condition is True
        ):
            # Bare ``@dec`` — args[0] is the function being decorated.
            setattr(
                args[0],
                attr,
                marker_cls(reason=None, condition=True),
            )
            return args[0]
        if args:
            raise TypeError(
                f'{decorator_name}() takes only keyword arguments; '
                f'got positional {args!r}'
            )
        marker = marker_cls(reason=reason, condition=condition)

        def wrap(func):
            setattr(func, attr, marker)
            return func

        return wrap

    decorator.__name__ = decorator_name
    decorator.__qualname__ = decorator_name
    return decorator


def active_marker(call, attr):
    """Return the marker on ``call`` if its condition resolves truthy.

    Resolves a callable ``condition`` by calling it. Returns ``None``
    when no marker is attached or the resolved condition is falsy.
    Exceptions raised while resolving the condition propagate to the
    caller, which is responsible for attributing them to the test.
    """
    marker = getattr(call, attr, None)
    if marker is None:
        return None
    cond = marker.condition
    if callable(cond):
        cond = cond()
    return marker if cond else None
