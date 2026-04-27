from assertions import test


@test
def free_function():
    assert True


@test
class ClassUnit:
    def method(self):
        assert True
