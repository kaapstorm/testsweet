TEST_MARKER = '__assertions_test__'


def test(func):
    setattr(func, TEST_MARKER, True)
    return func
