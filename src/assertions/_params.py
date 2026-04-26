from typing import Callable, Iterable

from assertions._markers import TEST_MARKER


PARAMS_MARKER = '__assertions_params__'


def test_params(args_iterable: Iterable) -> Callable:
    materialized = tuple(args_iterable)

    def decorator(func: Callable) -> Callable:
        setattr(func, TEST_MARKER, True)
        setattr(func, PARAMS_MARKER, materialized)
        return func

    return decorator


def test_params_lazy(args_iterable: Iterable) -> Callable:
    def decorator(func: Callable) -> Callable:
        setattr(func, TEST_MARKER, True)
        setattr(func, PARAMS_MARKER, args_iterable)
        return func

    return decorator
