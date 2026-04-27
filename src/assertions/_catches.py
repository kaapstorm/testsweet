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
