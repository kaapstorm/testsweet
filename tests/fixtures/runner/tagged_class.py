from testsweet import tag, test


@test
@tag('slow')
class SlowSuite:
    def alpha(self):
        pass

    @tag('db')
    def beta(self):
        pass


@test
class Untagged:
    @tag('db')
    def gamma(self):
        pass

    def delta(self):
        pass


@test
@tag('slow')
def lone_function():
    pass


@test
def untagged_function():
    pass
