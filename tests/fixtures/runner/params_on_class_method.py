from testsweet import test, test_params


@test
class Cls:
    @test_params([(1, 2), (3, 4)])
    def method(self, a, b):
        assert a < b
