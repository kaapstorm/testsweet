import importlib
import unittest
from contextlib import AbstractContextManager

from assertions._resolve import resolve_units


class TestResolveUnits(unittest.TestCase):
    def test_plain_function_yields_one_pair(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.all_pass',
        )
        generators = resolve_units(mod)
        self.assertEqual(len(generators), 2)
        first_pairs = list(generators[0])
        self.assertEqual(len(first_pairs), 1)
        name, call = first_pairs[0]
        self.assertEqual(name, 'passes_one')
        self.assertIs(
            call,
            getattr(mod, 'passes_one'),
        )

    def test_parameterized_function_yields_indexed_partials(self):
        import functools

        mod = importlib.import_module(
            'tests.fixtures.runner.params_simple',
        )
        generators = resolve_units(mod)
        self.assertEqual(len(generators), 1)
        pairs = list(generators[0])
        names = [name for name, _ in pairs]
        self.assertEqual(names, ['adds[0]', 'adds[1]'])
        for _, call in pairs:
            self.assertIsInstance(call, functools.partial)

    def test_class_with_context_manager_brackets_methods(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.class_calls_recorded',
        )
        mod.CALLS.clear()
        generators = resolve_units(mod)
        self.assertEqual(len(generators), 1)
        # Consuming the generator should run __enter__ once before
        # any method, and __exit__ once after the last method.
        for _name, call in generators[0]:
            call()
        self.assertEqual(
            mod.CALLS,
            ['enter', 'first', 'second', 'exit'],
        )

    def test_class_without_context_manager_runs_methods(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.class_simple',
        )
        generators = resolve_units(mod)
        self.assertEqual(len(generators), 1)
        pairs = list(generators[0])
        names = [name for name, _ in pairs]
        self.assertEqual(names, ['Simple.first', 'Simple.second'])

    def test_class_method_selector_filters(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.class_simple',
        )
        generators = resolve_units(mod, names=['Simple.first'])
        self.assertEqual(len(generators), 1)
        pairs = list(generators[0])
        names = [name for name, _ in pairs]
        self.assertEqual(names, ['Simple.first'])

    def test_unmatched_name_raises_lookup_error(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.all_pass',
        )
        with self.assertRaises(LookupError) as ctx:
            resolve_units(mod, names=['nonexistent'])
        self.assertIn('nonexistent', str(ctx.exception))

    def test_validation_runs_before_any_iteration(self):
        # If any name is unmatched, no generator is created or
        # iterated. The class_calls_recorded fixture would record
        # 'enter' if its generator were started; verify CALLS stays
        # empty when LookupError fires.
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
        generators = resolve_units(
            mod,
            names=['Simple', 'Simple.first'],
        )
        pairs = list(generators[0])
        names = [name for name, _ in pairs]
        # Both methods run, not just the one named in the selector.
        self.assertEqual(names, ['Simple.first', 'Simple.second'])

    def test_mixed_module_yields_one_generator_per_unit(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.class_mixed_with_function',
        )
        generators = resolve_units(mod)
        self.assertEqual(len(generators), 2)
        all_names = []
        for gen in generators:
            for name, _ in gen:
                all_names.append(name)
        self.assertEqual(
            all_names,
            ['free_function', 'ClassUnit.method'],
        )

    def test_empty_module_returns_empty_list(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.empty',
        )
        self.assertEqual(resolve_units(mod), [])

    def test_no_names_means_no_filtering(self):
        # When names is None, every discovered unit appears.
        mod = importlib.import_module(
            'tests.fixtures.runner.has_failure',
        )
        generators = resolve_units(mod)
        all_names = []
        for gen in generators:
            for name, _ in gen:
                all_names.append(name)
        self.assertEqual(all_names, ['passes', 'fails'])


if __name__ == '__main__':
    unittest.main()
