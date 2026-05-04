from testsweet import params, test


@test
@params([])
def never_runs(a):
    raise AssertionError('should not run')
