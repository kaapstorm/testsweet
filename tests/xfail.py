from testsweet import test
from testsweet._catches import catch_exceptions
from testsweet._markers import XFAIL_MARKER
from testsweet._xfail import XFailMarker, xfail


@test
class XFailDecorator:
    def bare_returns_same_function(self):
        def f():
            pass

        assert xfail(f) is f

    def bare_attaches_marker_with_no_reason(self):
        @xfail
        def f():
            pass

        marker = getattr(f, XFAIL_MARKER)
        assert marker == XFailMarker(reason=None, condition=True)

    def called_with_reason(self):
        @xfail(reason='see #42')
        def f():
            pass

        marker = getattr(f, XFAIL_MARKER)
        assert marker.reason == 'see #42'
        assert marker.condition is True

    def called_with_condition_true(self):
        @xfail(condition=True)
        def f():
            pass

        marker = getattr(f, XFAIL_MARKER)
        assert marker.condition is True

    def called_with_condition_false_still_attaches_marker(self):
        @xfail(condition=False)
        def f():
            pass

        marker = getattr(f, XFAIL_MARKER)
        assert marker.condition is False

    def called_with_condition_callable_stored_as_is(self):
        def cond() -> bool:
            return True

        @xfail(condition=cond)
        def f():
            pass

        marker = getattr(f, XFAIL_MARKER)
        assert marker.condition is cond

    def called_with_reason_and_condition(self):
        @xfail(condition=True, reason='windows-broken')
        def f():
            pass

        marker = getattr(f, XFAIL_MARKER)
        assert marker.reason == 'windows-broken'
        assert marker.condition is True

    def stray_positional_raises_type_error(self):
        with catch_exceptions() as caught:
            xfail('a', 'b')
        assert len(caught) == 1
        assert isinstance(caught[0], TypeError)
        assert 'positional' in str(caught[0])

    def decorated_function_still_callable(self):
        @xfail
        def f():
            return 'hi'

        assert f() == 'hi'

    def marker_dataclass_is_frozen(self):
        marker = XFailMarker(reason=None, condition=True)
        with catch_exceptions() as caught:
            marker.reason = 'mutate'  # ty: ignore[invalid-assignment]
        assert len(caught) == 1

    def marker_dataclass_has_no_strict_field(self):
        # The spec deliberately omits the strict field.
        marker = XFailMarker(reason=None, condition=True)
        assert not hasattr(marker, 'strict')


@test
class XFailMarkerConstant:
    def name_is_dunder_testsweet_xfail(self):
        assert XFAIL_MARKER == '__testsweet_xfail__'
