"""Outcome sentinel classes for non-pass/fail test results.

These are constructed (not raised) by the runner and placed into the
result tuple. The reporter dispatches on ``isinstance`` to format them.
They subclass ``Exception`` so the existing
``list[tuple[str, Exception | None]]`` result shape doesn't have to
change.
"""


class Skipped(Exception):
    """Placed in the result slot when ``@skip`` is active."""

    def __init__(self, reason: str | None = None):
        self.reason = reason
        super().__init__(reason or '')


class XFailed(Exception):
    """Placed in the result slot when ``@xfail`` is active and the
    test raised the expected failure."""

    def __init__(self, actual: Exception, reason: str | None = None):
        self.actual = actual
        self.reason = reason
        super().__init__(reason or repr(actual))


class XPassed(Exception):
    """Placed in the result slot when ``@xfail`` is active but the
    test unexpectedly passed.

    Treated as a failure for exit-code purposes.
    """

    def __init__(self, reason: str | None = None):
        self.reason = reason
        super().__init__(reason or '')
