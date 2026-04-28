from testsweet import test


class _Base:
    def base_method(self):
        assert True

    def overridden(self):
        raise AssertionError('base override should not run')


@test
class Leaf(_Base):
    def leaf_method(self):
        assert True

    def overridden(self):
        assert True
