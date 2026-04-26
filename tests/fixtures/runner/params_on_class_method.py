from assertions import Test, test_params


class Cls(Test):
    @test_params([(1, 2), (3, 4)])
    def method(self, a, b):
        assert a < b
