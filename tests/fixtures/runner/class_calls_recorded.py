from contextlib import AbstractContextManager

from testsweet import test


CALLS: list[str] = []


@test
class Recorded(AbstractContextManager):
    def __enter__(self):
        CALLS.append('enter')

    def __exit__(self, exc_type, exc, tb):
        CALLS.append('exit')

    def first(self):
        CALLS.append('first')

    def second(self):
        CALLS.append('second')
