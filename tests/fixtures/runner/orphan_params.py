from testsweet import params


@params([(1,), (2,)])
def orphan(a):
    assert a > 0
