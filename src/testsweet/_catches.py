import warnings
from types import TracebackType


class catch_exceptions:
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
        try:
            assert self._records is not None
            for r in self._records:
                # `WarningMessage.message` is typed `Warning | str` in
                # the stdlib stubs (since `warnings.warn` accepts a
                # bare string), but the warnings machinery normalizes
                # to a Warning before recording. Narrow for mypy.
                assert isinstance(r.message, Warning)
                self._warns.append(r.message)
        finally:
            assert self._catcher is not None
            self._catcher.__exit__(None, None, None)
        return None
