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


if __name__ == '__main__':
    unittest.main()
