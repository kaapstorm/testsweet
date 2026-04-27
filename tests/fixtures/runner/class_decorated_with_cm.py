from contextlib import AbstractContextManager

from assertions import test


CALLS: list[str] = []


@test
class WithCM(AbstractContextManager):
    def __enter__(self):
        CALLS.append('enter')
        self.value = 1
        return self

    def __exit__(self, exc_type, exc, tb):
        CALLS.append('exit')

    def uses_fixture(self):
        CALLS.append('test')
        assert self.value == 1
