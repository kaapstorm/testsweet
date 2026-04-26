from assertions import Test


class Simple(Test):
    def first(self):
        assert 1 + 1 == 2

    def second(self):
        assert 'a' + 'b' == 'ab'
