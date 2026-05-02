"""Plugin protocol and loader.

Plugins are discovered via the ``testsweet.plugins`` entry-point group. A
plugin is any module-like object that may expose either of two callables:

* ``session()`` returns a context manager that wraps the entire test run.
  Use for one-time setup/teardown such as creating a test database.
* ``unit(name)`` returns a context manager that wraps a single test unit
  call. Use for per-test isolation such as transaction rollback.

Both are optional. A plugin missing either hook is simply skipped for
that phase.

Example registration in a plugin package's ``pyproject.toml``::

    [project.entry-points."testsweet.plugins"]
    django = "testsweet_django"
"""
from contextlib import AbstractContextManager, ExitStack, contextmanager
from importlib.metadata import entry_points
from typing import Iterator, Protocol, runtime_checkable

ENTRY_POINT_GROUP = 'testsweet.plugins'


@runtime_checkable
class Plugin(Protocol):
    def session(self) -> AbstractContextManager[None]: ...
    def unit(self, name: str) -> AbstractContextManager[None]: ...


def load_plugins() -> list[object]:
    return [ep.load() for ep in entry_points(group=ENTRY_POINT_GROUP)]


@contextmanager
def session(plugins: list[object]) -> Iterator[None]:
    with ExitStack() as stack:
        for plugin in plugins:
            hook = getattr(plugin, 'session', None)
            if hook is not None:
                stack.enter_context(hook())
        yield


@contextmanager
def unit(plugins: list[object], name: str) -> Iterator[None]:
    with ExitStack() as stack:
        for plugin in plugins:
            hook = getattr(plugin, 'unit', None)
            if hook is not None:
                stack.enter_context(hook(name))
        yield
