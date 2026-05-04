import importlib

from testsweet import ConfigurationError, discover, params, test
from testsweet._catches import catch_exceptions


@test
class Discover:
    @params(
        [
            ('tests.fixtures.empty', []),
            ('tests.fixtures.single', ['only_test']),
            ('tests.fixtures.multiple', ['a', 'b', 'c']),
            (
                'tests.fixtures.mixed',
                ['decorated_one', 'decorated_two'],
            ),
            ('tests.fixtures.non_callable_marker', []),
            ('tests.fixtures.imported_only', ['only_test']),
            # `from ... import only_test` runs before `local_after` is
            # defined, so vars() insertion order is imported-first.
            (
                'tests.fixtures.mixed_local_imported',
                ['only_test', 'local_after'],
            ),
        ]
    )
    def names_match_fixture(self, module_name, expected):
        mod = importlib.import_module(module_name)
        result = discover(mod)
        assert [f.__name__ for f in result] == expected

    def returns_fresh_list_each_call(self):
        mod = importlib.import_module('tests.fixtures.multiple')
        first = discover(mod)
        first.clear()
        second = discover(mod)
        assert [f.__name__ for f in second] == ['a', 'b', 'c']

    def returns_test_params_decorated_function(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.params_simple',
        )
        result = discover(mod)
        names = [f.__name__ for f in result]
        assert 'adds' in names


@test
class OrphanModifierMarkers:
    @params(
        [
            ('tests.fixtures.runner.orphan_params',),
            ('tests.fixtures.runner.orphan_skip',),
            ('tests.fixtures.runner.orphan_xfail',),
            ('tests.fixtures.runner.orphan_tag',),
        ]
    )
    def discover_raises_configuration_error(self, module_name):
        mod = importlib.import_module(module_name)
        with catch_exceptions() as excs:
            discover(mod)
        assert len(excs) == 1
        assert isinstance(excs[0], ConfigurationError)
        assert 'orphan' in str(excs[0])

    def test_plus_params_discovers_normally(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.params_simple',
        )
        result = discover(mod)
        assert [f.__name__ for f in result] == ['adds']
