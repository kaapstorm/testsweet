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

_GREEN = '32'
_YELLOW = '33'
_RED = '31'
_BOLD_RED = '1;31'
_MAGENTA = '35'


def _c(text: str, code: str, enabled: bool) -> str:
    return f'\033[{code}m{text}\033[0m' if enabled else text


_XPASS_DETAIL = (
    'Test was marked @xfail but passed. '
    'Either remove the marker or fix the test.'
)


def _suffix(reason: str | None) -> str:
    return f': {reason}' if reason else ''


def format_result_line(
    full_name: str,
    outcome: Outcome,
    use_color: bool = False,
) -> str:
    """One-line summary suitable for streaming output."""
    match outcome:
        case Passed():
            status = _c('ok', _GREEN, use_color)
            return f'{full_name} ... {status}'
        case Skipped(reason=reason):
            status = _c(f'skipped{_suffix(reason)}', _YELLOW, use_color)
            return f'{full_name} ... {status}'
        case XFailed(reason=reason):
            status = _c(f'xfailed{_suffix(reason)}', _YELLOW, use_color)
            return f'{full_name} ... {status}'
        case XPassed(reason=reason):
            status = _c(f'XPASSED{_suffix(reason)}', _MAGENTA, use_color)
            return f'{full_name} ... {status}'
        case Failed(exc=exc):
            detail = str(exc) or assertion_source(exc) or ''
            status = _c(f'FAIL: AssertionError: {detail}', _BOLD_RED, use_color)
            return f'{full_name} ... {status}'
        case Errored(exc=exc):
            status = _c(
                f'ERROR: {type(exc).__name__}: {exc}', _RED, use_color,
            )
            return f'{full_name} ... {status}'


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
    ('passed', 'passed', _GREEN),
    ('failed', 'failed', _BOLD_RED),
    ('errored', 'error', _RED),
    ('skipped', 'skipped', _YELLOW),
    ('xfailed', 'xfailed', _YELLOW),
    ('xpassed', 'xpassed', _MAGENTA),
)


def summarize(
    results: Iterable[tuple[str, Outcome]],
    use_color: bool = False,
) -> str:
    """One-line summary of result counts."""
    counts: collections.Counter = collections.Counter()
    total = 0
    for _name, outcome in results:
        counts[_outcome_key(outcome)] += 1
        total += 1
    if total == 0:
        return '0 tests'
    parts = [
        _c(f'{counts[key]} {label}', color, use_color)
        for key, label, color in _SUMMARY_ORDER
        if counts.get(key)
    ]
    return ', '.join(parts)
