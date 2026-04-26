from assertions import test, test_params


@test
def plain():
    assert True


@test_params([(1, 1, 2)])
def parameterized(a, b, expected):
    assert a + b == expected
