from assertions import test


@test
class WithUnderscores:
    def _helper(self):
        raise AssertionError('helper should not run')

    def _data(self):
        raise AssertionError('data should not run')

    def public(self):
        assert True
