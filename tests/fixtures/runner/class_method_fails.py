from assertions import Test


class HasFailure(Test):
    def passes(self):
        assert True

    def fails(self):
        assert 1 == 2
