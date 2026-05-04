from testsweet import params, test
from testsweet._xfail import xfail


@test
@xfail(reason='maybe broken')
@params([(1,), (2,)])
def parametrized(x):
    # Raises for x == 1, passes for x == 2.
    if x == 1:
        raise ValueError('boom')
