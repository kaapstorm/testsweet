from contextlib import AbstractContextManager

from assertions import test


@test
class ExitRaises(AbstractContextManager):
    def __exit__(self, exc_type, exc, tb):
        raise RuntimeError('boom in exit')

    def passes(self):
        assert True
