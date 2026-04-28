from testsweet import test


@test
class Simple:
    def passes(self):
        assert True

    def fails(self):
        assert False
