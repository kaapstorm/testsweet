import importlib

from testsweet import discover, test


@test
class Discover:
    def single_decorated_function(self):
        mod = importlib.import_module('tests.fixtures.single')
        result = discover(mod)
        assert [f.__name__ for f in result] == ['only_test']

    def multiple_in_definition_order(self):
        mod = importlib.import_module('tests.fixtures.multiple')
        result = discover(mod)
        assert [f.__name__ for f in result] == ['a', 'b', 'c']

    def skips_undecorated_functions(self):
        mod = importlib.import_module('tests.fixtures.mixed')
        result = discover(mod)
        assert [f.__name__ for f in result] == [
            'decorated_one',
            'decorated_two',
        ]

    def skips_non_callable_marker_holder(self):
        mod = importlib.import_module(
            'tests.fixtures.non_callable_marker',
        )
        result = discover(mod)
        assert result == []

    def includes_imported_test_functions(self):
        mod = importlib.import_module('tests.fixtures.imported_only')
        result = discover(mod)
        assert [f.__name__ for f in result] == ['only_test']

    def mixed_local_and_imported_in_vars_order(self):
        mod = importlib.import_module(
            'tests.fixtures.mixed_local_imported',
        )
        result = discover(mod)
        # `from ... import only_test` runs before `local_after` is
        # defined, so vars() insertion order is imported-first.
        assert [f.__name__ for f in result] == [
            'only_test',
            'local_after',
        ]

    def empty_module_returns_empty_list(self):
        mod = importlib.import_module('tests.fixtures.empty')
        result = discover(mod)
        assert result == []

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
