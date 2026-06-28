from testsweet import test


@test
def passing_and_loud():
    print('SECRET_PASS_OUTPUT')
    assert True


@test
def failing_and_loud():
    print('SECRET_FAIL_OUTPUT')
    assert False
