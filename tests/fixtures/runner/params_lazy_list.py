from testsweet import params_lazy, test


@test
@params_lazy([(1, 1), (2, 2)])
def equals(a, b):
    assert a == b
