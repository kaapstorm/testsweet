from contextlib import AbstractContextManager, contextmanager

from testsweet import test


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
        self.db = None

    def __enter__(self):
        self.db = {}
        return self

    def __exit__(self, exc_type, exc, tb):
        self.db = None
        return None

    @contextmanager
    def __test_context__(self):
        # Context applied to all test methods
        self.db['foo'] = 1
        try:
            yield
        finally:
            del self.db['foo']

    @contextmanager
    def _bar_fixture(self):
        # Context available to any test methods
        self.db['bar'] = 2
        try:
            yield
        finally:
            del self.db['bar']

    def has_foo(self):
        # Uses both fixtures
        assert 'foo' in self.db
        with self._bar_fixture():
            assert 'bar' in self.db
        assert 'bar' not in self.db
