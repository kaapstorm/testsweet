from testsweet import params, test


@test
class Cls:
    @params([(1, 2), (3, 4)])
    def method(self, a, b):
        assert a < b
