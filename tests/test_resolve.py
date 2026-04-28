import functools
import importlib
import unittest

from testsweet._resolve import resolve_units


class TestResolveUnits(unittest.TestCase):
    def test_plain_function_yields_one_pair(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.all_pass',
        )
        pairs = list(resolve_units(mod))
        names = [name for name, _ in pairs]
        self.assertEqual(names, ['passes_one', 'passes_two'])
        # The first pair's callable is the function itself.
        self.assertIs(pairs[0][1], getattr(mod, 'passes_one'))

    def test_parameterized_function_yields_indexed_partials(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.params_simple',
        )
        pairs = list(resolve_units(mod))
        names = [name for name, _ in pairs]
        self.assertEqual(names, ['adds[0]', 'adds[1]'])
        for _, call in pairs:
            self.assertIsInstance(call, functools.partial)

    def test_class_with_context_manager_brackets_methods(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.class_calls_recorded',
        )
        mod.CALLS.clear()
        # Iterating the flat iterator runs __enter__ once before any
        # method call and __exit__ once after the last method.
        for _name, call in resolve_units(mod):
            call()
        self.assertEqual(
            mod.CALLS,
            ['enter', 'first', 'second', 'exit'],
        )

    def test_class_without_context_manager_runs_methods(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.class_simple',
        )
        names = [name for name, _ in resolve_units(mod)]
        self.assertEqual(names, ['Simple.first', 'Simple.second'])

    def test_class_method_selector_filters(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.class_simple',
        )
        names = [
            name for name, _ in resolve_units(mod, names=['Simple.first'])
        ]
        self.assertEqual(names, ['Simple.first'])

    def test_unmatched_name_raises_lookup_error(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.all_pass',
        )
        with self.assertRaises(LookupError) as ctx:
            resolve_units(mod, names=['nonexistent'])
        self.assertIn('nonexistent', str(ctx.exception))

    def test_validation_runs_before_any_iteration(self):
        # If any name is unmatched, the iterator is never advanced
        # because LookupError is raised at resolve_units(...) call
        # time, before chain.from_iterable is constructed.
        mod = importlib.import_module(
            'tests.fixtures.runner.class_calls_recorded',
        )
        mod.CALLS.clear()
        with self.assertRaises(LookupError):
            resolve_units(
                mod,
                names=['Recorded.first', 'Recorded.nonexistent'],
            )
        self.assertEqual(mod.CALLS, [])

    def test_class_form_wins_over_method_selector(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.class_simple',
        )
        names = [
            name
            for name, _ in resolve_units(
                mod,
                names=['Simple', 'Simple.first'],
            )
        ]
        # Both methods run, not just the one named in the selector.
        self.assertEqual(names, ['Simple.first', 'Simple.second'])

    def test_mixed_module_yields_pairs_in_order(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.class_mixed_with_function',
        )
        names = [name for name, _ in resolve_units(mod)]
        self.assertEqual(
            names,
            ['free_function', 'ClassUnit.method'],
        )

    def test_empty_module_returns_empty_iterator(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.empty',
        )
        self.assertEqual(list(resolve_units(mod)), [])

    def test_no_names_means_no_filtering(self):
        # When names is None, every discovered unit appears.
        mod = importlib.import_module(
            'tests.fixtures.runner.has_failure',
        )
        names = [name for name, _ in resolve_units(mod)]
        self.assertEqual(names, ['passes', 'fails'])


if __name__ == '__main__':
    unittest.main()
