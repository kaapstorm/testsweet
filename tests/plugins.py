from contextlib import contextmanager
from types import SimpleNamespace

from testsweet import ConfigurationError, catch_exceptions, test
from testsweet._plugins import (
    Plugin,
    load_plugins,
    session_for,
    unit_wrapper,
)


def _make_plugin(
    on_session=None,
    on_unit=None,
):
    @contextmanager
    def session_cm():
        if on_session is not None:
            on_session('enter')
        try:
            yield
        finally:
            if on_session is not None:
                on_session('exit')

    @contextmanager
    def unit_cm(name):
        if on_unit is not None:
            on_unit(name, 'enter')
        try:
            yield
        finally:
            if on_unit is not None:
                on_unit(name, 'exit')

    return SimpleNamespace(session=session_cm, unit=unit_cm)


@test
class SessionFor:
    def empty_plugins_is_noop(self):
        with session_for([]):
            pass

    def session_hook_runs(self):
        events: list[str] = []
        plugin = _make_plugin(on_session=events.append)
        with session_for([plugin]):
            events.append('inside')
        assert events == ['enter', 'inside', 'exit']

    def multiple_plugins_nest_in_order(self):
        events: list[str] = []
        plugin_a = _make_plugin(
            on_session=lambda phase: events.append(f'a-{phase}'),
        )
        plugin_b = _make_plugin(
            on_session=lambda phase: events.append(f'b-{phase}'),
        )
        with session_for([plugin_a, plugin_b]):
            events.append('inside')
        assert events == [
            'a-enter', 'b-enter', 'inside', 'b-exit', 'a-exit',
        ]


@test
class UnitWrapper:
    def empty_plugins_yields_noop(self):
        wrap = unit_wrapper([])
        with wrap('some.test'):
            pass

    def unit_hook_receives_test_name(self):
        seen: list[tuple[str, str]] = []
        plugin = _make_plugin(
            on_unit=lambda name, phase: seen.append((name, phase)),
        )
        wrap = unit_wrapper([plugin])
        with wrap('mod.test_thing'):
            pass
        assert seen == [
            ('mod.test_thing', 'enter'),
            ('mod.test_thing', 'exit'),
        ]

    def wrapper_is_reusable_across_tests(self):
        seen: list[str] = []
        plugin = _make_plugin(
            on_unit=lambda name, phase: seen.append(f'{name}-{phase}'),
        )
        wrap = unit_wrapper([plugin])
        with wrap('first'):
            pass
        with wrap('second'):
            pass
        assert seen == [
            'first-enter', 'first-exit',
            'second-enter', 'second-exit',
        ]


@test
class PluginProtocolCheck:
    def conforming_plugin_passes_isinstance(self):
        plugin = _make_plugin()
        assert isinstance(plugin, Plugin)

    def missing_session_fails_isinstance(self):
        @contextmanager
        def unit_cm(name):
            yield

        plugin = SimpleNamespace(unit=unit_cm)
        assert not isinstance(plugin, Plugin)

    def missing_unit_fails_isinstance(self):
        @contextmanager
        def session_cm():
            yield

        plugin = SimpleNamespace(session=session_cm)
        assert not isinstance(plugin, Plugin)


@test
class LoadPlugins:
    @contextmanager
    def __test_context__(self):
        from testsweet import _plugins
        original = _plugins.entry_points
        try:
            yield
        finally:
            _plugins.entry_points = original

    def loads_conforming_plugin(self):
        from testsweet import _plugins
        plugin = _make_plugin()
        fake_ep = SimpleNamespace(
            name='fake',
            value='fake_module',
            load=lambda: plugin,
        )
        _plugins.entry_points = lambda group: [fake_ep]
        loaded = load_plugins()
        assert loaded == [plugin]

    def rejects_plugin_missing_unit(self):
        from testsweet import _plugins

        @contextmanager
        def session_cm():
            yield

        bad = SimpleNamespace(session=session_cm)
        fake_ep = SimpleNamespace(
            name='broken',
            value='broken_module',
            load=lambda: bad,
        )
        _plugins.entry_points = lambda group: [fake_ep]
        with catch_exceptions() as excs:
            load_plugins()
        assert len(excs) == 1
        assert isinstance(excs[0], ConfigurationError)
        assert 'broken' in str(excs[0])

    def empty_entry_points_yields_empty_list(self):
        from testsweet import _plugins
        _plugins.entry_points = lambda group: []
        assert load_plugins() == []

    def import_failure_raises_configuration_error(self):
        from testsweet import _plugins

        def raises():
            raise ImportError('boom')

        fake_ep = SimpleNamespace(
            name='broken',
            value='broken_module',
            load=raises,
        )
        _plugins.entry_points = lambda group: [fake_ep]
        with catch_exceptions() as excs:
            load_plugins()
        assert len(excs) == 1
        assert isinstance(excs[0], ConfigurationError)
        assert 'broken' in str(excs[0])
        assert 'boom' in str(excs[0])
