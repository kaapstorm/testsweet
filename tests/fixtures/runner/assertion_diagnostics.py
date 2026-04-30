from testsweet import test


@test
def compare_vars():
    foo = 1
    bar = 0
    assert foo == bar


@test
def with_message():
    assert 1 == 2, 'explicit message'


@test
def bare_name():
    flag = False
    assert flag


@test
def bool_op():
    a = 1
    b = 2
    assert a > b and b > 0
