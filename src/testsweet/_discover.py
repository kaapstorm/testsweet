"""Discover ``@test``-marked callables and classes in a module."""
from types import ModuleType
from typing import Callable

from testsweet._config import ConfigurationError
from testsweet._markers import (
    SKIP_MARKER,
    TAGS_MARKER,
    TEST_MARKER,
    XFAIL_MARKER,
)
from testsweet._params import PARAMS_MARKER


_MODIFIER_MARKERS = (PARAMS_MARKER, SKIP_MARKER, XFAIL_MARKER, TAGS_MARKER)


def discover(module: ModuleType) -> list[Callable]:
    """Return module-level callables marked as test units.

    Order follows ``vars(module)`` (definition order on CPython 3.7+).
    Useful when embedding testsweet in a custom runner.

    Raises ``ConfigurationError`` if a module-level callable carries a
    testsweet modifier marker (``@params``, ``@skip``, ``@xfail``,
    ``@tag``) without ``@test``.
    """
    tests: list[Callable] = []
    for name, value in vars(module).items():
        if not callable(value):
            continue
        is_test = getattr(value, TEST_MARKER, False) is True
        orphan = next(
            (m for m in _MODIFIER_MARKERS if hasattr(value, m)),
            None,
        )
        if orphan is not None and not is_test:
            raise ConfigurationError(
                f'{module.__name__}.{name} has testsweet modifier '
                f'{orphan} but is not decorated with @test.'
            )
        if is_test:
            tests.append(value)
    return tests
