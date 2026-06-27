"""Outcome sum type for test results.

``run()`` returns a ``list[tuple[str, Outcome]]``. Each outcome is one
of the frozen dataclasses below; consumers dispatch via ``match`` or
``isinstance``. Outcomes are values, not exceptions — the runner
constructs them; nothing raises them.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Passed:
    """The test ran and returned without raising."""


@dataclass(frozen=True)
class Failed:
    """The test raised ``AssertionError``."""

    exc: AssertionError


@dataclass(frozen=True)
class Errored:
    """The test raised an exception other than ``AssertionError``.

    Also used when an active ``@skip`` or ``@xfail`` callable
    condition raised while being evaluated.
    """

    exc: Exception


@dataclass(frozen=True)
class Skipped:
    """An active ``@skip`` marker prevented the test from running."""

    reason: str | None = None


@dataclass(frozen=True)
class XFailed:
    """An ``@xfail``-marked test raised the expected failure."""

    actual: Exception
    reason: str | None = None


@dataclass(frozen=True)
class XPassed:
    """An ``@xfail``-marked test unexpectedly passed.

    Treated as a failure for exit-code purposes: either the underlying
    bug has been fixed (remove the marker) or the test was wrongly
    marked.
    """

    reason: str | None = None


Outcome = Passed | Failed | Errored | Skipped | XFailed | XPassed


@dataclass(frozen=True)
class Result:
    """A test unit's outcome plus any output it produced.

    ``run()`` returns ``list[Result]``. ``stdout`` and ``stderr`` hold
    the test's captured streams; they are empty unless the unit wrote
    to those streams. Captured output is replayed only when the test
    fails — see ``_report.print_failure_detail``.
    """

    name: str
    outcome: Outcome
    stdout: str = ''
    stderr: str = ''
