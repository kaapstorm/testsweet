import importlib
import unittest

from testsweet import discover


class TestDiscover(unittest.TestCase):
    def test_single_decorated_function(self):
        mod = importlib.import_module('tests.fixtures.single')
        result = discover(mod)
        self.assertEqual([f.__name__ for f in result], ['only_test'])

    def test_multiple_in_definition_order(self):
        mod = importlib.import_module('tests.fixtures.multiple')
        result = discover(mod)
        self.assertEqual([f.__name__ for f in result], ['a', 'b', 'c'])

    def test_skips_undecorated_functions(self):
        mod = importlib.import_module('tests.fixtures.mixed')
        result = discover(mod)
        self.assertEqual(
            [f.__name__ for f in result],
            ['decorated_one', 'decorated_two'],
        )

    def test_skips_non_callable_marker_holder(self):
        mod = importlib.import_module(
            'tests.fixtures.non_callable_marker',
        )
        result = discover(mod)
        self.assertEqual(result, [])

    def test_includes_imported_test_functions(self):
        mod = importlib.import_module('tests.fixtures.imported_only')
        result = discover(mod)
        self.assertEqual([f.__name__ for f in result], ['only_test'])

    def test_mixed_local_and_imported_in_vars_order(self):
        mod = importlib.import_module(
            'tests.fixtures.mixed_local_imported',
        )
        result = discover(mod)
        # `from ... import only_test` runs before `local_after` is
        # defined, so vars() insertion order is imported-first.
        self.assertEqual(
            [f.__name__ for f in result],
            ['only_test', 'local_after'],
        )

    def test_empty_module_returns_empty_list(self):
        mod = importlib.import_module('tests.fixtures.empty')
        result = discover(mod)
        self.assertEqual(result, [])

    def test_returns_fresh_list_each_call(self):
        mod = importlib.import_module('tests.fixtures.multiple')
        first = discover(mod)
        first.clear()
        second = discover(mod)
        self.assertEqual([f.__name__ for f in second], ['a', 'b', 'c'])

    def test_returns_test_params_decorated_function(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.params_simple',
        )
        result = discover(mod)
        names = [f.__name__ for f in result]
        self.assertIn('adds', names)


if __name__ == '__main__':
    unittest.main()
