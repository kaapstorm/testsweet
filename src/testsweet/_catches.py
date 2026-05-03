"""Context managers that capture exceptions and warnings."""
import warnings
from types import TracebackType
from typing import cast


class catch_exceptions:
    """Capture exceptions raised inside the ``with`` block.

    Yields a list to which any caught ``Exception`` is appended; the
    exception does not propagate. ``BaseException`` subclasses that are
    not ``Exception`` (e.g. ``KeyboardInterrupt``) are not captured.
    """

    def __init__(self) -> None:
        self._excs: list[Exception] = []

    def __enter__(self) -> list[Exception]:
        return self._excs

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> bool:
        if exc is None:
            return False
        if isinstance(exc, Exception):
            self._excs.append(exc)
            return True
        return False


class catch_warnings:
    """Capture warnings emitted inside the ``with`` block.

    Yields a list to which each ``Warning`` is appended.
    """

    def __init__(self) -> None:
        self._warns: list[Warning] = []
        self._catcher: warnings.catch_warnings | None = None
        self._records: list[warnings.WarningMessage] | None = None

    def __enter__(self) -> list[Warning]:
        self._catcher = warnings.catch_warnings(
            record=True,
            action='always',
        )
        self._records = self._catcher.__enter__()
        return self._warns

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        records = self._records
        catcher = self._catcher
        if records is None or catcher is None:
            # __exit__ called without __enter__; protocol violation.
            return None
        try:
            for record in records:
                # WarningMessage.message is typed Warning | str in the
                # stdlib stubs (since warnings.warn accepts a bare
                # string), but the warnings machinery normalizes to a
                # Warning before recording.
                self._warns.append(cast(Warning, record.message))
        finally:
            catcher.__exit__(None, None, None)
        return None
