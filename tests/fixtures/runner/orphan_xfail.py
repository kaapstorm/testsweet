from testsweet._xfail import xfail


@xfail(reason='expected to fail')
def orphan():
    raise AssertionError('boom')
