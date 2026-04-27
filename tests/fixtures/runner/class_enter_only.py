from assertions import test


@test
class EnterOnly:
    def __enter__(self):
        return self

    def never_runs(self):
        raise AssertionError('should not run')
