import importlib

from testsweet import discover, test, test_params


@test
class Discover:
    @test_params(
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
