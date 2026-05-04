from testsweet import params, test
from testsweet._skip import skip


CALLS: list[tuple[int]] = []


@test
@skip(reason='blocked')
@params([(1,), (2,)])
def parametrized(x):
    CALLS.append((x,))
