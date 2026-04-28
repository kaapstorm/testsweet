from testsweet import test_params


@test_params([(1, 1, 2), (1, 1, 99), (2, 3, 5)])
def adds(a, b, expected):
    assert a + b == expected
