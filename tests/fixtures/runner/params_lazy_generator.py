from testsweet import test_params_lazy


def get_args():
    for i in range(3):
        yield (i, i + 1, 2 * i + 1)


@test_params_lazy(get_args())
def adds(a, b, expected):
    assert a + b == expected
