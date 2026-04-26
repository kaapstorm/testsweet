import importlib
import unittest

from assertions import run


class TestRun(unittest.TestCase):
    def test_single_passing_test(self):
        mod = importlib.import_module('tests.fixtures.runner.all_pass')
        results = run(mod)
        self.assertEqual(len(results), 2)
        for _, exc in results:
            self.assertIsNone(exc)

    def test_single_failing_assert(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.has_failure',
        )
        results = run(mod)
        self.assertEqual(results[0][0], 'passes')
        self.assertIsNone(results[0][1])
        self.assertEqual(results[1][0], 'fails')
        self.assertIsInstance(results[1][1], AssertionError)

    def test_results_in_discover_order(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.has_failure',
        )
        results = run(mod)
        self.assertEqual(
            [name for name, _ in results],
            ['passes', 'fails'],
        )

    def test_empty_module_returns_empty_list(self):
        mod = importlib.import_module('tests.fixtures.runner.empty')
        results = run(mod)
        self.assertEqual(results, [])

    def test_non_assertion_exception_is_caught(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.non_assertion_error',
        )
        results = run(mod)
        self.assertEqual(len(results), 1)
        name, exc = results[0]
        self.assertEqual(name, 'raises_value_error')
        self.assertIsInstance(exc, ValueError)

    def test_keyboard_interrupt_propagates(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.keyboard_interrupt',
        )
        with self.assertRaises(KeyboardInterrupt):
            run(mod)


class TestRunClass(unittest.TestCase):
    def test_class_with_passing_methods(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.class_simple',
        )
        results = run(mod)
        self.assertEqual(len(results), 2)
        names = [name for name, _ in results]
        self.assertEqual(names, ['Simple.first', 'Simple.second'])
        for _, exc in results:
            self.assertIsNone(exc)

    def test_underscore_methods_are_skipped(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.class_with_underscore_methods',
        )
        results = run(mod)
        names = [name for name, _ in results]
        self.assertEqual(names, ['WithUnderscores.public'])

    def test_enter_and_exit_run_around_methods(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.class_calls_recorded',
        )
        mod.CALLS.clear()
        run(mod)
        self.assertEqual(
            mod.CALLS,
            ['enter', 'first', 'second', 'exit'],
        )

    def test_failing_method_does_not_abort_class(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.class_method_fails',
        )
        results = run(mod)
        self.assertEqual(len(results), 2)
        names = [name for name, _ in results]
        self.assertEqual(
            names,
            ['HasFailure.passes', 'HasFailure.fails'],
        )
        self.assertIsNone(results[0][1])
        self.assertIsInstance(results[1][1], AssertionError)

    def test_enter_exception_propagates(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.class_enter_raises',
        )
        with self.assertRaises(RuntimeError):
            run(mod)

    def test_exit_exception_propagates(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.class_exit_raises',
        )
        with self.assertRaises(RuntimeError):
            run(mod)

    def test_mixed_function_and_class_in_vars_order(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.class_mixed_with_function',
        )
        results = run(mod)
        names = [name for name, _ in results]
        self.assertEqual(
            names,
            ['free_function', 'ClassUnit.method'],
        )


class TestRunParamsEager(unittest.TestCase):
    def test_runs_each_tuple_in_order(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.params_simple',
        )
        results = run(mod)
        names = [name for name, _ in results]
        self.assertEqual(names, ['adds[0]', 'adds[1]'])
        for _, exc in results:
            self.assertIsNone(exc)

    def test_failure_recorded_at_correct_index(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.params_with_failure',
        )
        results = run(mod)
        names = [name for name, _ in results]
        self.assertEqual(
            names,
            ['adds[0]', 'adds[1]', 'adds[2]'],
        )
        self.assertIsNone(results[0][1])
        self.assertIsInstance(results[1][1], AssertionError)
        self.assertIsNone(results[2][1])

    def test_empty_param_list_produces_no_results(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.params_empty',
        )
        self.assertEqual(run(mod), [])

    def test_function_without_params_unchanged(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.params_no_decoration',
        )
        results = run(mod)
        names = [name for name, _ in results]
        self.assertEqual(names, ['plain', 'parameterized[0]'])
        for _, exc in results:
            self.assertIsNone(exc)

    def test_accepts_generator(self):
        # The generator was consumed at decoration time, so the second
        # run() call sees the same materialized tuple.
        mod = importlib.import_module(
            'tests.fixtures.runner.params_generator',
        )
        first = run(mod)
        second = run(mod)
        self.assertEqual(
            [name for name, _ in first],
            ['adds[0]', 'adds[1]', 'adds[2]'],
        )
        self.assertEqual(
            [name for name, _ in second],
            ['adds[0]', 'adds[1]', 'adds[2]'],
        )

    def test_on_class_method(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.params_on_class_method',
        )
        results = run(mod)
        names = [name for name, _ in results]
        self.assertEqual(
            names,
            ['Cls.method[0]', 'Cls.method[1]'],
        )
        for _, exc in results:
            self.assertIsNone(exc)


class TestRunParamsLazy(unittest.TestCase):
    def test_runs_each_yielded_tuple(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.params_lazy_generator',
        )
        # Re-import so the module-level generator is freshly created
        # — earlier tests in this class consume it.
        importlib.reload(mod)
        results = run(mod)
        names = [name for name, _ in results]
        self.assertEqual(
            names,
            ['adds[0]', 'adds[1]', 'adds[2]'],
        )
        for _, exc in results:
            self.assertIsNone(exc)

    def test_generator_is_consumed_after_first_run(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.params_lazy_generator',
        )
        importlib.reload(mod)
        first = run(mod)
        second = run(mod)
        self.assertEqual(len(first), 3)
        self.assertEqual(second, [])

    def test_list_is_idempotent(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.params_lazy_list',
        )
        importlib.reload(mod)
        first = run(mod)
        second = run(mod)
        names_first = [name for name, _ in first]
        names_second = [name for name, _ in second]
        self.assertEqual(names_first, ['equals[0]', 'equals[1]'])
        self.assertEqual(names_second, ['equals[0]', 'equals[1]'])

    def test_on_class_method(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.params_lazy_on_class_method',
        )
        importlib.reload(mod)
        results = run(mod)
        names = [name for name, _ in results]
        self.assertEqual(
            names,
            ['Cls.method[0]', 'Cls.method[1]'],
        )
        for _, exc in results:
            self.assertIsNone(exc)


if __name__ == '__main__':
    unittest.main()
