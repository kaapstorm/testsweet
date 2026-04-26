from assertions import test


@test
def passes():
    assert True


@test
def fails():
    assert 1 == 2
