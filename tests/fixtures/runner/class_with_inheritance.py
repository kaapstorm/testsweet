from assertions import Test


class _Base(Test):
    def base_method(self):
        assert True

    def overridden(self):
        raise AssertionError('base override should not run')


class Leaf(_Base):
    def leaf_method(self):
        assert True

    def overridden(self):
        assert True
