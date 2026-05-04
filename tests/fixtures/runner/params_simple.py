from testsweet import params, test


@test
@params([(1, 1, 2), (2, 3, 5)])
def adds(a, b, expected):
    assert a + b == expected
