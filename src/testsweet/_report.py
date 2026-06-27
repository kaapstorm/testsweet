"""Format and print test results.

Kept separate from ``__main__`` so a future JSON/TAP/CI reporter can
slot in without forking ``main()``.
"""
import collections
import sys
import traceback
from typing import Iterable, TextIO

from testsweet._assertion import assertion_source, explain_assertion
from testsweet._outcomes import (
    Errored,
    Failed,
    Outcome,
    Passed,
    Skipped,
    XFailed,
    XPassed,
)


_XPASS_DETAIL = (
    'Test was marked @xfail but passed. '
    'Either remove the marker or fix the test.'
)


def _suffix(reason: str | None) -> str:
    return f': {reason}' if reason else ''


def format_result_line(full_name: str, outcome: Outcome) -> str:
    """One-line summary suitable for streaming output."""
    match outcome:
        case Passed():
            return f'{full_name} ... ok'
        case Skipped(reason=reason):
            return f'{full_name} ... skipped{_suffix(reason)}'
        case XFailed(reason=reason):
            return f'{full_name} ... xfailed{_suffix(reason)}'
        case XPassed(reason=reason):
            return f'{full_name} ... XPASSED{_suffix(reason)}'
        case Failed(exc=exc):
            detail = str(exc) or assertion_source(exc) or ''
            return f'{full_name} ... FAIL: AssertionError: {detail}'
        case Errored(exc=exc):
            return (
                f'{full_name} ... ERROR: {type(exc).__name__}: {exc}'
            )


def print_failure_detail(
    full_name: str,
    outcome: Outcome,
    file: TextIO = sys.stdout,
) -> None:
    """Multi-line failure block.

    Fires only for ``Failed``, ``Errored``, and ``XPassed``. Other
    outcomes do not get a detail block.
    """
    match outcome:
        case Passed() | Skipped() | XFailed():
            return
        case XPassed():
            print(file=file)
            print('=' * 70, file=file)
            print(f'XPASSED: {full_name}', file=file)
            print('-' * 70, file=file)
            print(_XPASS_DETAIL, file=file)
            return
        case Failed(exc=exc):
            _print_traceback_block('FAIL', full_name, exc, file)
            explanation = explain_assertion(exc)
            if explanation is not None:
                print(explanation, file=file)
        case Errored(exc=exc):
            _print_traceback_block('ERROR', full_name, exc, file)


def _print_traceback_block(
    label: str,
    full_name: str,
    exc: Exception,
    file: TextIO,
) -> None:
    print(file=file)
    print('=' * 70, file=file)
    print(f'{label}: {full_name}', file=file)
    print('-' * 70, file=file)
    tb = exc.__traceback__.tb_next if exc.__traceback__ else None
    traceback.print_exception(type(exc), exc, tb, file=file)


def _outcome_key(outcome: Outcome) -> str:
    match outcome:
        case Passed():
            return 'passed'
        case Failed():
            return 'failed'
        case Errored():
            return 'errored'
        case Skipped():
            return 'skipped'
        case XFailed():
            return 'xfailed'
        case XPassed():
            return 'xpassed'


_SUMMARY_ORDER = (
    ('passed', 'passed'),
    ('failed', 'failed'),
    ('errored', 'error'),
    ('skipped', 'skipped'),
    ('xfailed', 'xfailed'),
    ('xpassed', 'xpassed'),
)


def summarize(results: Iterable[tuple[str, Outcome]]) -> str:
    """One-line summary of result counts."""
    counts: collections.Counter = collections.Counter()
    total = 0
    for _name, outcome in results:
        counts[_outcome_key(outcome)] += 1
        total += 1
    if total == 0:
        return '0 tests'
    parts = [
        f'{counts[key]} {label}'
        for key, label in _SUMMARY_ORDER
        if counts.get(key)
    ]
    return ', '.join(parts)
