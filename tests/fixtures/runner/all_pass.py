from testsweet import test


@test
def passes_one():
    assert 1 + 1 == 2


@test
def passes_two():
    assert 'a' + 'b' == 'ab'
