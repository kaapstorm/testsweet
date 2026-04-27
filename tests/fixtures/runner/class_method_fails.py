from assertions import test


@test
class HasFailure:
    def passes(self):
        assert True

    def fails(self):
        assert 1 == 2
