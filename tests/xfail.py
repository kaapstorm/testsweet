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

    def called_with_if_true(self):
        @xfail(if_=True)
        def f():
            pass

        marker = getattr(f, XFAIL_MARKER)
        assert marker.condition is True

    def called_with_if_false_still_attaches_marker(self):
        @xfail(if_=False)
        def f():
            pass

        marker = getattr(f, XFAIL_MARKER)
        assert marker.condition is False

    def called_with_if_truthy_value_coerced_to_bool(self):
        @xfail(if_='non-empty')
        def f():
            pass

        marker = getattr(f, XFAIL_MARKER)
        assert marker.condition is True

    def called_with_if_falsy_value_coerced_to_bool(self):
        @xfail(if_=0)
        def f():
            pass

        marker = getattr(f, XFAIL_MARKER)
        assert marker.condition is False

    def called_with_reason_and_if_(self):
        @xfail(if_=True, reason='windows-broken')
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

    def decorated_function_still_callable(self):
        @xfail
        def f():
            return 'hi'

        assert f() == 'hi'

    def marker_dataclass_is_frozen(self):
        marker = XFailMarker(reason=None, condition=True)
        with catch_exceptions() as caught:
            marker.reason = 'mutate'  # type: ignore[misc]
        assert len(caught) == 1

    def marker_dataclass_has_no_strict_field(self):
        # The spec deliberately omits the strict field.
        marker = XFailMarker(reason=None, condition=True)
        assert not hasattr(marker, 'strict')


@test
class XFailMarkerConstant:
    def name_is_dunder_testsweet_xfail(self):
        assert XFAIL_MARKER == '__testsweet_xfail__'
