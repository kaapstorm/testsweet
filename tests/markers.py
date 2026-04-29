from testsweet import test
from testsweet._markers import TEST_MARKER


@test
class Decorator:
    def returns_same_function_object(self):
        def f():
            pass

        assert test(f) is f

    def sets_marker_attribute_to_true(self):
        @test
        def f():
            pass

        assert getattr(f, TEST_MARKER) is True

    def decorated_function_still_runs_and_returns_value(self):
        @test
        def f():
            return 42

        assert f() == 42

    def undecorated_function_has_no_marker(self):
        def f():
            pass

        assert not hasattr(f, TEST_MARKER)

    def marker_name_constant(self):
        assert TEST_MARKER == '__testsweet_test__'
