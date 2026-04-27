from assertions import test, test_params_lazy


@test
class Cls:
    @test_params_lazy([(1, 2), (3, 4)])
    def method(self, a, b):
        assert a < b
