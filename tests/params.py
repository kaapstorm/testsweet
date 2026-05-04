from testsweet import (
    params,
    params_lazy,
    test,
    test_params,
    test_params_lazy,
)
from testsweet._markers import TEST_MARKER
from testsweet._params import PARAMS_MARKER


@test
class ParamsEager:
    def returns_same_function_object(self):
        def f(a, b):
            pass

        decorated = params([(1, 2)])(f)
        assert decorated is f

    def does_not_set_test_marker(self):
        @params([(1,)])
        def f(a):
            pass

        assert not getattr(f, TEST_MARKER, False)

    def stores_params_as_tuple_matching_iterable(self):
        @params([(1, 2), (3, 4)])
        def f(a, b):
            pass

        assert getattr(f, PARAMS_MARKER) == ((1, 2), (3, 4))

    def generator_is_eagerly_materialized(self):
        def gen():
            for i in range(3):
                yield (i,)

        @params(gen())
        def f(a):
            pass

        assert getattr(f, PARAMS_MARKER) == ((0,), (1,), (2,))

    def decorated_function_still_callable(self):
        @params([(1, 2)])
        def f(a, b):
            return a + b

        assert f(1, 2) == 3


@test
class ParamsLazy:
    def returns_same_function_object(self):
        def f(a, b):
            pass

        decorated = params_lazy([(1, 2)])(f)
        assert decorated is f

    def does_not_set_test_marker(self):
        @params_lazy([(1,)])
        def f(a):
            pass

        assert not getattr(f, TEST_MARKER, False)

    def stores_iterable_by_identity(self):
        args = [(1, 2), (3, 4)]

        @params_lazy(args)
        def f(a, b):
            pass

        assert getattr(f, PARAMS_MARKER) is args

    def generator_is_stored_unconsumed(self):
        def gen():
            for i in range(3):
                yield (i,)

        g = gen()

        @params_lazy(g)
        def f(a):
            pass

        assert getattr(f, PARAMS_MARKER) is g

    def decorated_function_still_callable(self):
        @params_lazy([(1, 2)])
        def f(a, b):
            return a + b

        assert f(1, 2) == 3


@test
class BackwardsCompatShims:
    def test_params_is_alias_of_params(self):
        assert test_params is params

    def test_params_lazy_is_alias_of_params_lazy(self):
        assert test_params_lazy is params_lazy
