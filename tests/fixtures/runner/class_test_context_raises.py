from contextlib import contextmanager

from testsweet import test


@test
class TestContextEnterRaises:
    @contextmanager
    def __test_context__(self):
        raise RuntimeError('enter failed')
        yield  # pragma: no cover

    def passes(self):
        pass


@test
class TestContextExitRaises:
    @contextmanager
    def __test_context__(self):
        try:
            yield
        finally:
            raise RuntimeError('exit failed')

    def passes(self):
        pass
