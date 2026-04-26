import importlib
import unittest

from assertions import run


class TestRun(unittest.TestCase):
    def test_single_passing_test(self):
        mod = importlib.import_module('tests.fixtures.runner.all_pass')
        results = run(mod)
        self.assertEqual(len(results), 2)
        for func, exc in results:
            self.assertIsNone(exc)

    def test_single_failing_assert(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.has_failure',
        )
        results = run(mod)
        names = [(f.__name__, exc) for f, exc in results]
        self.assertEqual(names[0][0], 'passes')
        self.assertIsNone(names[0][1])
        self.assertEqual(names[1][0], 'fails')
        self.assertIsInstance(names[1][1], AssertionError)

    def test_results_in_discover_order(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.has_failure',
        )
        results = run(mod)
        self.assertEqual(
            [f.__name__ for f, _ in results],
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
        func, exc = results[0]
        self.assertEqual(func.__name__, 'raises_value_error')
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
        names = [bound.__qualname__ for bound, _ in results]
        self.assertEqual(names, ['Simple.first', 'Simple.second'])
        for _, exc in results:
            self.assertIsNone(exc)

    def test_underscore_methods_are_skipped(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.class_with_underscore_methods',
        )
        results = run(mod)
        names = [bound.__name__ for bound, _ in results]
        self.assertEqual(names, ['public'])

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
        names = [bound.__name__ for bound, _ in results]
        self.assertEqual(names, ['passes', 'fails'])
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
        names = [bound.__qualname__ for bound, _ in results]
        self.assertEqual(
            names,
            ['free_function', 'ClassUnit.method'],
        )


if __name__ == '__main__':
    unittest.main()
