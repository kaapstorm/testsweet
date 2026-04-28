import warnings

from testsweet import catch_exceptions, catch_warnings, test


@test
class CatchExceptions:
    def captures_exception_instance(self):
        with catch_exceptions() as excs:
            raise ValueError('boom')
        assert len(excs) == 1
        assert isinstance(excs[0], ValueError)
        assert str(excs[0]) == 'boom'

    def captures_subclass_of_exception(self):
        class MyError(ValueError):
            pass

        with catch_exceptions() as excs:
            raise MyError('subclass')
        assert len(excs) == 1
        assert isinstance(excs[0], MyError)

    def propagates_keyboard_interrupt(self):
        captured: list[Exception] = []
        outer: list[BaseException] = []
        try:
            with catch_exceptions() as excs:
                captured = excs
                raise KeyboardInterrupt
        except KeyboardInterrupt as exc:
            outer.append(exc)
        assert len(outer) == 1
        assert captured == []

    def empty_when_body_returns_normally(self):
        with catch_exceptions() as excs:
            x = 1 + 1  # noqa: F841
        assert excs == []

    def list_is_empty_inside_block_before_raise(self):
        observed_inside = None
        with catch_exceptions() as excs:
            observed_inside = list(excs)
            raise ValueError('boom')
        assert observed_inside == []
        assert len(excs) == 1


@test
class CatchWarnings:
    def captures_single_warning(self):
        with catch_warnings() as warns:
            warnings.warn('hello', DeprecationWarning)
        assert len(warns) == 1
        assert type(warns[0]) is DeprecationWarning
        assert 'hello' in str(warns[0])

    def captures_multiple_warnings_in_emission_order(self):
        with catch_warnings() as warns:
            warnings.warn('first', DeprecationWarning)
            warnings.warn('second', UserWarning)
            warnings.warn('third', DeprecationWarning)
        assert len(warns) == 3
        assert type(warns[0]) is DeprecationWarning
        assert type(warns[1]) is UserWarning
        assert type(warns[2]) is DeprecationWarning
        assert 'first' in str(warns[0])
        assert 'second' in str(warns[1])
        assert 'third' in str(warns[2])

    def empty_when_no_warnings(self):
        with catch_warnings() as warns:
            x = 1 + 1  # noqa: F841
        assert warns == []

    def exception_propagates_with_warnings_already_captured(self):
        warns_ref = None
        with catch_exceptions() as excs:
            with catch_warnings() as warns:
                warns_ref = warns
                warnings.warn('before raise', DeprecationWarning)
                raise ValueError('boom')
        assert len(excs) == 1
        assert isinstance(excs[0], ValueError)
        assert warns_ref is not None
        assert len(warns_ref) == 1
        assert type(warns_ref[0]) is DeprecationWarning
        assert 'before raise' in str(warns_ref[0])

    def outer_filter_error_does_not_escalate_inside(self):
        with warnings.catch_warnings():
            warnings.simplefilter('error')
            with catch_warnings() as warns:
                warnings.warn('caught', DeprecationWarning)
        assert len(warns) == 1
        assert type(warns[0]) is DeprecationWarning

    def outer_filter_ignore_does_not_silence_inside(self):
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            with catch_warnings() as warns:
                warnings.warn('caught', DeprecationWarning)
        assert len(warns) == 1
        assert type(warns[0]) is DeprecationWarning
