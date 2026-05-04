"""Decorators for parametrized tests."""
from typing import Callable, Iterable


PARAMS_MARKER = '__testsweet_params__'


def params(args_iterable: Iterable) -> Callable:
    """Run the decorated function once per tuple in ``args_iterable``.

    The iterable is consumed eagerly at decoration time. Each tuple is
    unpacked as positional arguments to the function.
    """
    materialized = tuple(args_iterable)

    def decorator(func: Callable) -> Callable:
        setattr(func, PARAMS_MARKER, materialized)
        return func

    return decorator


def params_lazy(args_iterable: Iterable) -> Callable:
    """Like ``params``, but the iterable is consumed at run time.

    Use this when materializing the parameters is expensive or has
    side effects that should be deferred.
    """
    def decorator(func: Callable) -> Callable:
        setattr(func, PARAMS_MARKER, args_iterable)
        return func

    return decorator
