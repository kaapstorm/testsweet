from testsweet import params_lazy, test


@test
class Cls:
    @params_lazy([(1, 2), (3, 4)])
    def method(self, a, b):
        assert a < b
