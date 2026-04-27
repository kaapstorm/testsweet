import warnings
from assertions import catch_exceptions, catch_warnings, test


@test
def zero_div():
    with catch_exceptions() as excs:
        1 / 0
    assert type(excs[0]) is ZeroDivisionError


@test
def deprecated():
    with catch_warnings() as warns:
        old_func()
    assert len(warns) == 1
    assert type(warns[0]) is DeprecationWarning
    assert 'new_func' in str(warns[0])


def old_func():
    warnings.warn('Use new_func', DeprecationWarning)
    pass
