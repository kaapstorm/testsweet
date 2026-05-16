from testsweet import test
from testsweet._catches import catch_exceptions
from testsweet._outcomes import (
    Errored,
    Failed,
    Passed,
    Skipped,
    XFailed,
    XPassed,
)


@test
class PassedOutcome:
    def is_a_dataclass(self):
        # Frozen, so equal instances compare equal.
        assert Passed() == Passed()

    def is_not_an_exception(self):
        assert not isinstance(Passed(), Exception)


@test
class FailedOutcome:
    def stores_exception(self):
        exc = AssertionError('1 == 2')
        out = Failed(exc)
        assert out.exc is exc

    def is_frozen(self):
        out = Failed(AssertionError())
        with catch_exceptions() as caught:
            out.exc = AssertionError()  # type: ignore[misc]  # ty: ignore[invalid-assignment]
        assert len(caught) == 1


@test
class ErroredOutcome:
    def stores_exception(self):
        exc = TypeError('nope')
        out = Errored(exc)
        assert out.exc is exc


@test
class SkippedOutcome:
    def stores_reason(self):
        s = Skipped('not yet implemented')
        assert s.reason == 'not yet implemented'

    def reason_defaults_to_none(self):
        s = Skipped()
        assert s.reason is None

    def is_not_an_exception(self):
        assert not isinstance(Skipped(), Exception)

    def is_frozen(self):
        s = Skipped('r')
        with catch_exceptions() as caught:
            s.reason = 'mutate'  # type: ignore[misc]  # ty: ignore[invalid-assignment]
        assert len(caught) == 1


@test
class XFailedOutcome:
    def stores_actual_and_reason(self):
        actual = ValueError('boom')
        x = XFailed(actual, 'see #42')
        assert x.actual is actual
        assert x.reason == 'see #42'

    def reason_defaults_to_none(self):
        x = XFailed(ValueError('boom'))
        assert x.reason is None

    def is_not_an_exception(self):
        assert not isinstance(XFailed(ValueError()), Exception)


@test
class XPassedOutcome:
    def stores_reason(self):
        x = XPassed('was-marked-broken')
        assert x.reason == 'was-marked-broken'

    def reason_defaults_to_none(self):
        x = XPassed()
        assert x.reason is None

    def is_not_an_exception(self):
        assert not isinstance(XPassed(), Exception)
