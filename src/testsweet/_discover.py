"""Discover ``@test``-marked callables and classes in a module."""
from types import ModuleType
from typing import Protocol

from testsweet._config import ConfigurationError
from testsweet._markers import (
    SKIP_MARKER,
    TAGS_MARKER,
    TEST_MARKER,
    XFAIL_MARKER,
)
from testsweet._params import PARAMS_MARKER


class TestUnit(Protocol):
    __name__: str
    __qualname__: str

    def __call__(self, *args, **kwargs): ...


_MODIFIER_DECORATORS = {
    PARAMS_MARKER: '@params',
    SKIP_MARKER: '@skip',
    XFAIL_MARKER: '@xfail',
    TAGS_MARKER: '@tag',
}


def discover(module: ModuleType) -> list[TestUnit]:
    """Return module-level callables marked as test units.

    Order follows ``vars(module)`` (definition order on CPython 3.7+).
    Useful when embedding testsweet in a custom runner.

    Raises ``ConfigurationError`` if a callable defined in this module
    carries a testsweet modifier marker (``@params``, ``@skip``,
    ``@xfail``, ``@tag``) without ``@test``. Imported callables are
    not checked — they were decorated wherever they were defined.
    """
    tests = []
    for name, value in vars(module).items():
        if not callable(value):
            continue
        is_test = getattr(value, TEST_MARKER, False) is True
        is_local = getattr(value, '__module__', None) == module.__name__
        if is_local and not is_test:
            orphan = next(
                (
                    friendly
                    for attr, friendly in _MODIFIER_DECORATORS.items()
                    if hasattr(value, attr)
                ),
                None,
            )
            if orphan is not None:
                raise ConfigurationError(
                    f'{module.__name__}.{name} has orphan {orphan} '
                    f'modifier but is not decorated with @test.'
                )
        if is_test:
            tests.append(value)
    return tests
