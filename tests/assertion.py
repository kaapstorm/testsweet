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


class _CountingAttr:
    """Counts ``.value`` accesses so a test can prove non-re-evaluation."""

    def __init__(self, value: object) -> None:
        self._value = value
        self.accesses = 0

    @property
    def value(self) -> object:
        self.accesses += 1
        return self._value


def _attr_fail(obj: _CountingAttr) -> None:
    assert obj.value == 99


class _CountingItem:
    """Counts ``__getitem__`` calls so a test can prove non-re-evaluation."""

    def __init__(self, value: object) -> None:
        self._value = value
        self.gets = 0

    def __getitem__(self, key: object) -> object:
        self.gets += 1
        return self._value


def _subscript_fail(box: _CountingItem) -> None:
    assert box['key'] == 99


class _AddRaisesOnSecond:
    """Adds normally once, then raises — to trip the explainer's re-eval.

    Unlike attribute/subscript access, a ``BinOp`` sub-expression is
    still re-evaluated, so this exercises the best-effort ``except``.
    """

    def __init__(self, value: int) -> None:
        self._value = value
        self._added = False

    def __add__(self, other: int) -> int:
        if self._added:
            raise RuntimeError('second add')
        self._added = True
        return self._value + other


def _binop_reeval_raises_fail(base: _AddRaisesOnSecond) -> None:
    extra = 1
    expected = 5
    assert expected == base + extra


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

    def does_not_reevaluate_attribute_access(self):
        # Attribute access can fire __getattr__/property side effects,
        # so it is skipped. obj.value was read once (in the real
        # assert) and not again.
        obj = _CountingAttr(1)
        exc = _capture(lambda: _attr_fail(obj))
        assert exc is not None
        result = explain_assertion(exc)
        assert obj.accesses == 1
        assert result is None

    def does_not_reevaluate_subscript_access(self):
        # Subscripting can fire __getitem__ side effects, so it is
        # skipped. box['key'] was read once (in the real assert).
        box = _CountingItem(1)
        exc = _capture(lambda: _subscript_fail(box))
        assert exc is not None
        result = explain_assertion(exc)
        assert box.gets == 1
        assert result is None

    def survives_a_sub_expression_that_raises_on_reeval(self):
        # A BinOp is still re-evaluated; base + extra raises the second
        # time (during explain). The explainer swallows that and still
        # reports the operand it could evaluate.
        base = _AddRaisesOnSecond(2)
        exc = _capture(lambda: _binop_reeval_raises_fail(base))
        assert exc is not None
        assert explain_assertion(exc) == '  expected = 5'

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
