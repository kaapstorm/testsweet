from contextlib import AbstractContextManager

from testsweet import test
from testsweet._skip import skip


CALLS: list[str] = []


@test
class Cls(AbstractContextManager):
    def __enter__(self):
        CALLS.append('enter')
        return self

    def __exit__(self, exc_type, exc, tb):
        CALLS.append('exit')

    @skip(reason='not yet')
    def skipped_method(self):
        CALLS.append('skipped_method')

    def runs(self):
        CALLS.append('runs')
