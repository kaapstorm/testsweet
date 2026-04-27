from contextlib import AbstractContextManager

from assertions import test


@test
class EnterRaises(AbstractContextManager):
    def __enter__(self):
        raise RuntimeError('boom in enter')

    def __exit__(self, exc_type, exc, tb):
        return None

    def never_runs(self):
        raise AssertionError('should not run')
