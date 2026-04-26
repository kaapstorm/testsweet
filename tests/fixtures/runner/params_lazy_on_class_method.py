from assertions import Test, test_params_lazy


class Cls(Test):
    @test_params_lazy([(1, 2), (3, 4)])
    def method(self, a, b):
        assert a < b
