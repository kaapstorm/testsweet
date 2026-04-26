from assertions._markers import TEST_MARKER


class Test:
    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        setattr(cls, TEST_MARKER, True)

    def __enter__(self) -> 'Test':
        return self

    def __exit__(
        self,
        exc_type: object,
        exc: object,
        tb: object,
    ) -> None:
        return None


def _public_methods(cls: type) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for klass in cls.__mro__:
        if klass is object:
            continue
        for name, value in vars(klass).items():
            if name.startswith('_'):
                continue
            if not callable(value):
                continue
            if name in seen:
                continue
            seen.add(name)
            out.append(name)
    return out
