TEST_MARKER = '__assertions_test__'


def test(target):
    """Mark a function or class as a test unit.

    Applied to a function, the function is discovered and run as a
    standalone test. Applied to a class, the class is discovered and
    its public methods are run as tests; if the class implements the
    context-manager protocol (`__enter__`/`__exit__`, typically by
    inheriting `contextlib.AbstractContextManager`), the runner enters
    it for the duration of its method invocations.
    """
    setattr(target, TEST_MARKER, True)
    return target
