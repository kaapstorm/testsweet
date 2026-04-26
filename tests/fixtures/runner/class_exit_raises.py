from assertions import Test


class ExitRaises(Test):
    def __exit__(self, exc_type, exc, tb):
        raise RuntimeError('boom in exit')

    def passes(self):
        assert True
