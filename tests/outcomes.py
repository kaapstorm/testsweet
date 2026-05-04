from testsweet import test
from testsweet._outcomes import Skipped, XFailed, XPassed


@test
class SkippedSentinel:
    def stores_reason(self):
        s = Skipped('not yet implemented')
        assert s.reason == 'not yet implemented'

    def reason_defaults_to_none(self):
        s = Skipped()
        assert s.reason is None

    def is_an_exception(self):
        assert isinstance(Skipped(), Exception)

    def is_not_an_assertion_error(self):
        assert not isinstance(Skipped(), AssertionError)

    def str_uses_reason_when_present(self):
        assert str(Skipped('because')) == 'because'

    def str_is_empty_when_no_reason(self):
        assert str(Skipped()) == ''


@test
class XFailedSentinel:
    def stores_actual_and_reason(self):
        actual = ValueError('boom')
        x = XFailed(actual, 'see #42')
        assert x.actual is actual
        assert x.reason == 'see #42'

    def reason_defaults_to_none(self):
        x = XFailed(ValueError('boom'))
        assert x.reason is None

    def is_an_exception(self):
        assert isinstance(XFailed(ValueError()), Exception)

    def is_not_an_assertion_error(self):
        assert not isinstance(XFailed(ValueError()), AssertionError)


@test
class XPassedSentinel:
    def stores_reason(self):
        x = XPassed('was-marked-broken')
        assert x.reason == 'was-marked-broken'

    def reason_defaults_to_none(self):
        x = XPassed()
        assert x.reason is None

    def is_an_exception(self):
        assert isinstance(XPassed(), Exception)

    def is_not_an_assertion_error(self):
        assert not isinstance(XPassed(), AssertionError)
