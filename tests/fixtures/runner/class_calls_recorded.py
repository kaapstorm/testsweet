from assertions import Test


CALLS: list[str] = []


class Recorded(Test):
    def __enter__(self):
        CALLS.append('enter')

    def __exit__(self, exc_type, exc, tb):
        CALLS.append('exit')

    def first(self):
        CALLS.append('first')

    def second(self):
        CALLS.append('second')
