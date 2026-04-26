from assertions import test_params


@test_params([])
def never_runs(a):
    raise AssertionError('should not run')
