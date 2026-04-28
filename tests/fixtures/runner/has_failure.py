from testsweet import test


@test
def passes():
    assert True


@test
def fails():
    assert 1 == 2
