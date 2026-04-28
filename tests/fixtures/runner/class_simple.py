from testsweet import test


@test
class Simple:
    def first(self):
        assert 1 + 1 == 2

    def second(self):
        assert 'a' + 'b' == 'ab'
