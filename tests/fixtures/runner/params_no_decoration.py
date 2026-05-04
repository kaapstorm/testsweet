from testsweet import params, test


@test
def plain():
    assert True


@test
@params([(1, 1, 2)])
def parameterized(a, b, expected):
    assert a + b == expected
