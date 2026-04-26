import unittest

from assertions import test_params, test_params_lazy
from assertions._markers import TEST_MARKER
from assertions._params import PARAMS_MARKER


class TestParamsEager(unittest.TestCase):
    def test_returns_same_function_object(self):
        def f(a, b):
            pass

        decorated = test_params([(1, 2)])(f)
        self.assertIs(decorated, f)

    def test_sets_test_marker(self):
        @test_params([(1,)])
        def f(a):
            pass

        self.assertIs(getattr(f, TEST_MARKER), True)

    def test_stores_params_as_tuple_matching_iterable(self):
        @test_params([(1, 2), (3, 4)])
        def f(a, b):
            pass

        self.assertEqual(
            getattr(f, PARAMS_MARKER),
            ((1, 2), (3, 4)),
        )

    def test_generator_is_eagerly_materialized(self):
        def gen():
            for i in range(3):
                yield (i,)

        @test_params(gen())
        def f(a):
            pass

        self.assertEqual(
            getattr(f, PARAMS_MARKER),
            ((0,), (1,), (2,)),
        )

    def test_decorated_function_still_callable(self):
        @test_params([(1, 2)])
        def f(a, b):
            return a + b

        self.assertEqual(f(1, 2), 3)


class TestParamsLazy(unittest.TestCase):
    def test_returns_same_function_object(self):
        def f(a, b):
            pass

        decorated = test_params_lazy([(1, 2)])(f)
        self.assertIs(decorated, f)

    def test_sets_test_marker(self):
        @test_params_lazy([(1,)])
        def f(a):
            pass

        self.assertIs(getattr(f, TEST_MARKER), True)

    def test_stores_iterable_by_identity(self):
        args = [(1, 2), (3, 4)]

        @test_params_lazy(args)
        def f(a, b):
            pass

        self.assertIs(getattr(f, PARAMS_MARKER), args)

    def test_generator_is_stored_unconsumed(self):
        def gen():
            for i in range(3):
                yield (i,)

        g = gen()

        @test_params_lazy(g)
        def f(a):
            pass

        self.assertIs(getattr(f, PARAMS_MARKER), g)

    def test_decorated_function_still_callable(self):
        @test_params_lazy([(1, 2)])
        def f(a, b):
            return a + b

        self.assertEqual(f(1, 2), 3)


if __name__ == '__main__':
    unittest.main()
