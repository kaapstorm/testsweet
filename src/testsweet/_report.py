"""Format and print test results.

Kept separate from ``__main__`` so a future JSON/TAP/CI reporter can
slot in without forking ``main()``.
"""
import sys
import traceback
from typing import TextIO

from testsweet._assertion import assertion_source, explain_assertion


def format_result_line(full_name: str, exc: Exception | None) -> str:
    """One-line summary suitable for streaming output."""
    if exc is None:
        return f'{full_name} ... ok'
    detail = str(exc)
    if not detail and isinstance(exc, AssertionError):
        detail = assertion_source(exc) or ''
    return f'{full_name} ... FAIL: {type(exc).__name__}: {detail}'


def print_failure_detail(
    full_name: str,
    exc: Exception,
    file: TextIO = sys.stdout,
) -> None:
    """Multi-line failure block: traceback plus assertion explanation."""
    print(file=file)
    print('=' * 70, file=file)
    print(f'FAIL: {full_name}', file=file)
    print('-' * 70, file=file)
    tb = exc.__traceback__.tb_next if exc.__traceback__ else None
    traceback.print_exception(type(exc), exc, tb, file=file)
    if isinstance(exc, AssertionError):
        explanation = explain_assertion(exc)
        if explanation is not None:
            print(explanation, file=file)
