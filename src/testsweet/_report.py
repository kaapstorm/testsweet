"""Format and print test results.

Kept separate from ``__main__`` so a future JSON/TAP/CI reporter can
slot in without forking ``main()``.
"""
import collections
import sys
import traceback
from typing import Iterable, TextIO

from testsweet._assertion import assertion_source, explain_assertion
from testsweet._outcomes import Skipped, XFailed, XPassed


_XPASS_DETAIL = (
    'Test was marked @xfail but passed. '
    'Either remove the marker or fix the test.'
)


def format_result_line(full_name: str, exc: Exception | None) -> str:
    """One-line summary suitable for streaming output."""
    if exc is None:
        return f'{full_name} ... ok'
    if isinstance(exc, Skipped):
        suffix = f': {exc.reason}' if exc.reason else ''
        return f'{full_name} ... skipped{suffix}'
    if isinstance(exc, XFailed):
        suffix = f': {exc.reason}' if exc.reason else ''
        return f'{full_name} ... xfailed{suffix}'
    if isinstance(exc, XPassed):
        suffix = f': {exc.reason}' if exc.reason else ''
        return f'{full_name} ... XPASSED{suffix}'
    label = 'FAIL' if isinstance(exc, AssertionError) else 'ERROR'
    detail = str(exc)
    if not detail and isinstance(exc, AssertionError):
        detail = assertion_source(exc) or ''
    return f'{full_name} ... {label}: {type(exc).__name__}: {detail}'


def print_failure_detail(
    full_name: str,
    exc: Exception,
    file: TextIO = sys.stdout,
) -> None:
    """Multi-line failure block.

    Fires only for FAIL (AssertionError), ERROR (other Exception), and
    XPASSED. Skipped and XFailed do not get a detail block.
    """
    if isinstance(exc, (Skipped, XFailed)):
        return
    if isinstance(exc, XPassed):
        print(file=file)
        print('=' * 70, file=file)
        print(f'XPASSED: {full_name}', file=file)
        print('-' * 70, file=file)
        print(_XPASS_DETAIL, file=file)
        return
    label = 'FAIL' if isinstance(exc, AssertionError) else 'ERROR'
    print(file=file)
    print('=' * 70, file=file)
    print(f'{label}: {full_name}', file=file)
    print('-' * 70, file=file)
    tb = exc.__traceback__.tb_next if exc.__traceback__ else None
    traceback.print_exception(type(exc), exc, tb, file=file)
    if isinstance(exc, AssertionError):
        explanation = explain_assertion(exc)
        if explanation is not None:
            print(explanation, file=file)


def _outcome_key(exc: Exception | None) -> str:
    if exc is None:
        return 'passed'
    if isinstance(exc, Skipped):
        return 'skipped'
    if isinstance(exc, XFailed):
        return 'xfailed'
    if isinstance(exc, XPassed):
        return 'xpassed'
    if isinstance(exc, AssertionError):
        return 'failed'
    return 'errored'


def summarize(
    results: Iterable[tuple[str, Exception | None]],
) -> str:
    """One-line summary of result counts."""
    counts: collections.Counter = collections.Counter()
    total = 0
    for _name, exc in results:
        counts[_outcome_key(exc)] += 1
        total += 1
    if total == 0:
        return '0 tests'
    parts = []
    order = (
        ('passed', 'passed'),
        ('failed', 'failed'),
        ('errored', 'error'),
        ('skipped', 'skipped'),
        ('xfailed', 'xfailed'),
        ('xpassed', 'xpassed'),
    )
    for key, label in order:
        if counts.get(key):
            parts.append(f'{counts[key]} {label}')
    return ', '.join(parts)
