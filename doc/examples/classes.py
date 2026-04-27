from contextlib import AbstractContextManager

from assertions import test


# Plain class: @test marks it; all public methods are tests.
@test
class OrThings:
    def __init__(self):
        self.dict1 = {'foo': 1}
        self.dict2 = {'bar': 2}

    def or_dicts(self):
        assert self.dict1 | self.dict2 == {'foo': 1, 'bar': 2}

    def _not_a_test(self):
        raise NotImplementedError


# Class fixture: implement the context-manager protocol. Inheriting
# AbstractContextManager is idiomatic but not required — the runner
# duck-types __enter__/__exit__.
@test
class UsesDatabase(AbstractContextManager):
    def __init__(self):
        self.db = {}

    def __enter__(self):
        self.db = {'foo': 1}
        return self

    def __exit__(self, exc_type, exc, tb):
        self.db.clear()
        return None

    def has_foo(self):
        assert 'foo' in self.db
