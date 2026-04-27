import warnings


class catch_exceptions:
    def __init__(self) -> None:
        self._excs: list[Exception] = []

    def __enter__(self) -> list[Exception]:
        return self._excs

    def __exit__(self, exc_type, exc, tb) -> bool:
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

    def __exit__(self, exc_type, exc, tb) -> None:
        try:
            assert self._records is not None
            self._warns.extend(r.message for r in self._records)
        finally:
            assert self._catcher is not None
            self._catcher.__exit__(None, None, None)
        return None
