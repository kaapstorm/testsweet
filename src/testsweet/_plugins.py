"""Plugin protocol and loader.

Plugins are discovered via the ``testsweet.plugins`` entry-point group. A
plugin is any module-like object that exposes both of:

* ``session()`` returns a context manager that wraps the entire test run.
  Use for one-time setup/teardown such as creating a test database.
* ``unit(name)`` returns a context manager that wraps a single test unit
  call. Use for per-test isolation such as transaction rollback.

Both are required. If a plugin doesn't need one, define a no-op:

    from contextlib import contextmanager

    @contextmanager
    def unit(name):
        yield

Example registration in a plugin package's ``pyproject.toml``::

    [project.entry-points."testsweet.plugins"]
    django = "testsweet_django"
"""
from contextlib import AbstractContextManager, ExitStack, contextmanager
from importlib.metadata import entry_points
from typing import Any, Callable, Iterator, Protocol, runtime_checkable

from testsweet._config import ConfigurationError

ENTRY_POINT_GROUP = 'testsweet.plugins'


@runtime_checkable
class Plugin(Protocol):
    def session(self) -> AbstractContextManager[Any]: ...
    def unit(self, name: str) -> AbstractContextManager[Any]: ...


def load_plugins() -> list[Plugin]:
    plugins: list[Plugin] = []
    for ep in entry_points(group=ENTRY_POINT_GROUP):
        try:
            plugin = ep.load()
        except Exception as exc:
            raise ConfigurationError(
                f'Failed to load plugin {ep.name!r} from {ep.value!r}: {exc}'
            ) from exc
        if not isinstance(plugin, Plugin):
            raise ConfigurationError(
                f'Plugin {ep.name!r} loaded from {ep.value!r} does not '
                f'expose both session() and unit(name); both are required.'
            )
        plugins.append(plugin)
    return plugins


@contextmanager
def session_for(plugins: list[Plugin]) -> Iterator[None]:
    """Composite context manager entering each plugin's session in order."""
    with ExitStack() as stack:
        for plugin in plugins:
            stack.enter_context(plugin.session())
        yield


def unit_wrapper(
    plugins: list[Plugin],
) -> Callable[[str], AbstractContextManager[None]]:
    """Build a callable that wraps each test in all plugins' unit hooks.

    The returned callable is suitable for ``run(..., wrap_unit=...)``.
    """

    @contextmanager
    def wrap_unit(name: str) -> Iterator[None]:
        with ExitStack() as stack:
            for plugin in plugins:
                stack.enter_context(plugin.unit(name))
            yield

    return wrap_unit
