from testsweet import test, test_params, test_params_lazy
from testsweet._markers import TEST_MARKER
from testsweet._params import PARAMS_MARKER


@test
class ParamsEager:
    def returns_same_function_object(self):
        def f(a, b):
            pass

        decorated = test_params([(1, 2)])(f)
        assert decorated is f

    def sets_test_marker(self):
        @test_params([(1,)])
        def f(a):
            pass

        assert getattr(f, TEST_MARKER) is True

    def stores_params_as_tuple_matching_iterable(self):
        @test_params([(1, 2), (3, 4)])
        def f(a, b):
            pass

        assert getattr(f, PARAMS_MARKER) == ((1, 2), (3, 4))

    def generator_is_eagerly_materialized(self):
        def gen():
            for i in range(3):
                yield (i,)

        @test_params(gen())
        def f(a):
            pass

        assert getattr(f, PARAMS_MARKER) == ((0,), (1,), (2,))

    def decorated_function_still_callable(self):
        @test_params([(1, 2)])
        def f(a, b):
            return a + b

        assert f(1, 2) == 3


@test
class ParamsLazy:
    def returns_same_function_object(self):
        def f(a, b):
            pass

        decorated = test_params_lazy([(1, 2)])(f)
        assert decorated is f

    def sets_test_marker(self):
        @test_params_lazy([(1,)])
        def f(a):
            pass

        assert getattr(f, TEST_MARKER) is True

    def stores_iterable_by_identity(self):
        args = [(1, 2), (3, 4)]

        @test_params_lazy(args)
        def f(a, b):
            pass

        assert getattr(f, PARAMS_MARKER) is args

    def generator_is_stored_unconsumed(self):
        def gen():
            for i in range(3):
                yield (i,)

        g = gen()

        @test_params_lazy(g)
        def f(a):
            pass

        assert getattr(f, PARAMS_MARKER) is g

    def decorated_function_still_callable(self):
        @test_params_lazy([(1, 2)])
        def f(a, b):
            return a + b

        assert f(1, 2) == 3
