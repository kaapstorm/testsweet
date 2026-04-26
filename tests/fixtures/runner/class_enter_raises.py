from assertions import Test


class EnterRaises(Test):
    def __enter__(self):
        raise RuntimeError('boom in enter')

    def never_runs(self):
        raise AssertionError('should not run')
