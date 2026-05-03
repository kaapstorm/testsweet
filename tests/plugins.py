from contextlib import contextmanager
from types import SimpleNamespace

from testsweet import test
from testsweet._plugins import session, unit


@test
class PluginSession:
    def empty_plugins_is_noop(self):
        with session([]):
            pass

    def session_hook_runs(self):
        events: list[str] = []

        @contextmanager
        def session_cm():
            events.append('enter')
            try:
                yield
            finally:
                events.append('exit')

        plugin = SimpleNamespace(session=session_cm)
        with session([plugin]):
            events.append('inside')
        assert events == ['enter', 'inside', 'exit']

    def plugin_without_session_is_skipped(self):
        plugin = SimpleNamespace()  # no session attr
        with session([plugin]):
            pass

    def multiple_plugins_nest_in_order(self):
        events: list[str] = []

        def make(name):
            @contextmanager
            def cm():
                events.append(f'{name}-enter')
                try:
                    yield
                finally:
                    events.append(f'{name}-exit')
            return SimpleNamespace(session=cm)

        with session([make('a'), make('b')]):
            events.append('inside')
        assert events == [
            'a-enter', 'b-enter', 'inside', 'b-exit', 'a-exit',
        ]


@test
class PluginUnit:
    def empty_plugins_is_noop(self):
        with unit([], 'some.test'):
            pass

    def unit_hook_receives_test_name(self):
        seen: list[str] = []

        @contextmanager
        def unit_cm(name):
            seen.append(name)
            yield

        plugin = SimpleNamespace(unit=unit_cm)
        with unit([plugin], 'mod.test_thing'):
            pass
        assert seen == ['mod.test_thing']

    def plugin_without_unit_is_skipped(self):
        plugin = SimpleNamespace()  # no unit attr
        with unit([plugin], 'name'):
            pass
