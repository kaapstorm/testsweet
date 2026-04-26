import unittest

from assertions import test
from assertions._markers import TEST_MARKER


class TestDecorator(unittest.TestCase):
    def test_returns_same_function_object(self):
        def f():
            pass

        self.assertIs(test(f), f)

    def test_sets_marker_attribute_to_true(self):
        @test
        def f():
            pass

        self.assertIs(getattr(f, TEST_MARKER), True)

    def test_decorated_function_still_runs_and_returns_value(self):
        @test
        def f():
            return 42

        self.assertEqual(f(), 42)

    def test_undecorated_function_has_no_marker(self):
        def f():
            pass

        self.assertFalse(hasattr(f, TEST_MARKER))

    def test_marker_name_constant(self):
        self.assertEqual(TEST_MARKER, '__assertions_test__')


if __name__ == '__main__':
    unittest.main()
