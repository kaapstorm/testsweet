"""Tests for the best-effort assertion explainer.

The explainer reads the source file named by a failing assertion's
traceback frame and re-evaluates sub-expressions in that frame. So the
helpers below define real ``assert`` statements *in this file* — when
called and caught, their tracebacks point back here and the explainer
can read the source it needs. Each helper keeps its ``assert`` on its
own line so ``_find_assert`` matches it unambiguously by line number.
"""
from typing import Callable

from testsweet import test
from testsweet._assertion import assertion_source, explain_assertion


def _capture(fn: Callable[[], object]) -> AssertionError | None:
    """Run ``fn`` and return the ``AssertionError`` it raises.

    The returned exception carries the ``__traceback__`` the explainer
    needs. Returns ``None`` if ``fn`` did not raise ``AssertionError``.
    """
    try:
        fn()
    except AssertionError as exc:
        return exc
    return None


def _eq_fail() -> None:
    a = 1
    b = 2
    assert a == b


def _const_fail() -> None:
    x = 7
    assert x == 100


def _bool_fail() -> None:
    x = 1
    y = 0
    assert x and y


def _unary_fail() -> None:
    flag = True
    assert not flag


def _dup_fail() -> None:
    n = 0
    assert n > 0 and n > 0  # noqa: PLR0124 — repeat is the point


def _call_fail(counter: Callable[[], bool]) -> None:
    assert counter()


class _RaiseOnSecondAccess:
    """Returns its value on first ``.value`` access, then raises.

    Lets a sub-expression succeed when the real ``assert`` runs but
    fail when the explainer re-evaluates it.
    """

    def __init__(self, value: object) -> None:
        self._value = value
        self._accessed = False

    @property
    def value(self) -> object:
        if self._accessed:
            raise RuntimeError('second access')
        self._accessed = True
        return self._value


def _reeval_raises_fail(box: _RaiseOnSecondAccess) -> None:
    x = 5
    assert x == box.value


def _missing_source_error() -> AssertionError | None:
    """An ``AssertionError`` whose traceback names a nonexistent file."""
    code = compile(
        'def boom():\n'
        '    a = 1\n'
        '    assert a == 2\n'
        'boom()\n',
        '/nonexistent/testsweet_fake_source.py',
        'exec',
    )
    try:
        exec(code, {})  # noqa: S102 — exercising a forged co_filename
    except AssertionError as exc:
        return exc
    return None


@test
class AssertionSource:
    def returns_the_unparsed_assert(self):
        exc = _capture(_eq_fail)
        assert exc is not None
        assert assertion_source(exc) == 'assert a == b'

    def returns_none_without_a_traceback(self):
        # A bare AssertionError has no __traceback__ to locate.
        assert assertion_source(AssertionError()) is None

    def returns_none_when_source_is_unreadable(self):
        exc = _missing_source_error()
        assert exc is not None
        assert assertion_source(exc) is None


@test
class ExplainAssertion:
    def shows_both_operands_of_a_comparison(self):
        exc = _capture(_eq_fail)
        assert exc is not None
        assert explain_assertion(exc) == '  a = 1\n  b = 2'

    def skips_constant_sub_expressions(self):
        # The literal 100 carries no information, so only x is shown.
        exc = _capture(_const_fail)
        assert exc is not None
        assert explain_assertion(exc) == '  x = 7'

    def shows_operands_of_a_boolean_op(self):
        exc = _capture(_bool_fail)
        assert exc is not None
        assert explain_assertion(exc) == '  x = 1\n  y = 0'

    def shows_the_operand_of_a_unary_op(self):
        exc = _capture(_unary_fail)
        assert exc is not None
        assert explain_assertion(exc) == '  flag = True'

    def deduplicates_repeated_sub_expressions(self):
        exc = _capture(_dup_fail)
        assert exc is not None
        assert explain_assertion(exc) == '  n > 0 = False'

    def does_not_reevaluate_call_sub_expressions(self):
        # Calls are skipped so the explainer never fires side effects a
        # second time. counter() ran once (in the real assert) only.
        calls: list[int] = []

        def counter() -> bool:
            calls.append(1)
            return False

        exc = _capture(lambda: _call_fail(counter))
        assert exc is not None
        result = explain_assertion(exc)
        assert calls == [1]
        assert result is None

    def survives_a_sub_expression_that_raises_on_reeval(self):
        # box.value raises the second time it is read (during explain);
        # the explainer swallows that and still reports the operand it
        # could evaluate.
        box = _RaiseOnSecondAccess(6)
        exc = _capture(lambda: _reeval_raises_fail(box))
        assert exc is not None
        assert explain_assertion(exc) == '  x = 5'

    def returns_none_when_nothing_is_informative(self):
        # All sub-expressions are calls/constants, so there is nothing
        # to show.
        exc = _capture(lambda: _call_fail(lambda: False))
        assert exc is not None
        assert explain_assertion(exc) is None

    def returns_none_when_source_is_unreadable(self):
        exc = _missing_source_error()
        assert exc is not None
        assert explain_assertion(exc) is None
