from testsweet._skip import skip


@skip(reason='not yet decorated')
def orphan():
    raise AssertionError('should not run')
