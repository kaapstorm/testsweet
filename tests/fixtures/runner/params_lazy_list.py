from testsweet import test_params_lazy


@test_params_lazy([(1, 1), (2, 2)])
def equals(a, b):
    assert a == b
