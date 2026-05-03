from contextlib import AbstractContextManager, contextmanager

from testsweet import test, test_params


CALLS: list[str] = []


@test
class Cls(AbstractContextManager):
    def __enter__(self):
        CALLS.append('enter')
        return self

    def __exit__(self, exc_type, exc, tb):
        CALLS.append('exit')
        return None

    @contextmanager
    def __test_context__(self):
        CALLS.append('ctx-enter')
        try:
            yield
        finally:
            CALLS.append('ctx-exit')

    @test_params([(1, 2), (3, 4)])
    def method(self, a, b):
        CALLS.append(f'method({a},{b})')
        assert a < b
