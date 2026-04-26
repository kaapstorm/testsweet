from assertions import Test, test


@test
def free_function():
    assert True


class ClassUnit(Test):
    def method(self):
        assert True
