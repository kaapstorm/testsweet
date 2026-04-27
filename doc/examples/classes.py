from contextlib import AbstractContextManager

from assertions import test


@test
class IdiomaticClassFixtures(AbstractContextManager):
    def __init__(self):
        self.dict1 = {'foo': 1}
        self.dict2 = {'bar': 2}
        self.db = {}

    # Test classes use context managers for class fixtures
    def __enter__(self):
        self.db = {'foo': 1}

    def __exit__(self, exc_type, exc_value, traceback):
        self.db.clear()

    # All public methods are identified as tests
    def or_dicts(self):
        assert self.dict1 | self.dict2 == {'foo': 1, 'bar': 2}

    def uses_database(self):
        assert 'foo' in self.db

    def _not_a_test(self):
        raise NotImplemented
