from contextlib import AbstractContextManager, contextmanager

from testsweet import test


CALLS: list[str] = []


@test
class WithTestContext(AbstractContextManager):
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

    def first(self):
        CALLS.append('first')

    def second(self):
        CALLS.append('second')


@test
class TestContextOnly:
    @contextmanager
    def __test_context__(self):
        CALLS.append('only-enter')
        try:
            yield
        finally:
            CALLS.append('only-exit')

    def alpha(self):
        CALLS.append('alpha')


class _Base(AbstractContextManager):
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return None

    @contextmanager
    def __test_context__(self):
        CALLS.append('base-ctx-enter')
        try:
            yield
        finally:
            CALLS.append('base-ctx-exit')


@test
class WithSuperChain(_Base):
    @contextmanager
    def __test_context__(self):
        with super().__test_context__():
            CALLS.append('child-ctx-enter')
            try:
                yield
            finally:
                CALLS.append('child-ctx-exit')

    def only(self):
        CALLS.append('only')
