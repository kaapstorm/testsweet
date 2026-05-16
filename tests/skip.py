from testsweet import test
from testsweet._catches import catch_exceptions
from testsweet._markers import SKIP_MARKER
from testsweet._skip import SkipMarker, skip


@test
class SkipDecorator:
    def bare_returns_same_function(self):
        def f():
            pass

        assert skip(f) is f

    def bare_attaches_marker_with_no_reason(self):
        @skip
        def f():
            pass

        marker = getattr(f, SKIP_MARKER)
        assert marker == SkipMarker(reason=None, condition=True)

    def called_with_reason(self):
        @skip(reason='waiting on upstream')
        def f():
            pass

        marker = getattr(f, SKIP_MARKER)
        assert marker.reason == 'waiting on upstream'
        assert marker.condition is True

    def called_with_condition_true(self):
        @skip(condition=True)
        def f():
            pass

        marker = getattr(f, SKIP_MARKER)
        assert marker.condition is True
        assert marker.reason is None

    def called_with_condition_false_still_attaches_marker(self):
        @skip(condition=False)
        def f():
            pass

        marker = getattr(f, SKIP_MARKER)
        assert marker.condition is False

    def called_with_condition_callable_stored_as_is(self):
        called: list[int] = []

        def cond() -> bool:
            called.append(1)
            return True

        @skip(condition=cond)
        def f():
            pass

        marker = getattr(f, SKIP_MARKER)
        # Decoration must not invoke the callable — that's deferred
        # until the runner evaluates the marker.
        assert called == []
        assert marker.condition is cond

    def called_with_reason_and_condition(self):
        @skip(condition=True, reason='POSIX-only')
        def f():
            pass

        marker = getattr(f, SKIP_MARKER)
        assert marker.reason == 'POSIX-only'
        assert marker.condition is True

    def stray_positional_raises_type_error(self):
        with catch_exceptions() as caught:
            skip('a', 'b')
        assert len(caught) == 1
        assert isinstance(caught[0], TypeError)
        assert 'positional' in str(caught[0])

    def positional_with_kwargs_raises_type_error(self):
        # ``skip(func, reason='x')`` is a misuse — the bare-form
        # detection requires no kwargs; otherwise the callable is just
        # a stray positional.
        def f():
            pass

        with catch_exceptions() as caught:
            skip(f, reason='oops')
        assert len(caught) == 1
        assert isinstance(caught[0], TypeError)

    def decorated_function_still_callable(self):
        @skip
        def f():
            return 'hi'

        assert f() == 'hi'

    def marker_dataclass_is_frozen(self):
        marker = SkipMarker(reason=None, condition=True)
        with catch_exceptions() as caught:
            marker.reason = 'mutate'  # ty: ignore[invalid-assignment]
        assert len(caught) == 1


@test
class SkipMarkerConstant:
    def name_is_dunder_testsweet_skip(self):
        assert SKIP_MARKER == '__testsweet_skip__'
