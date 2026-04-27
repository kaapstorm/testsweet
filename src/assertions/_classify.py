import importlib
from types import ModuleType


def _resolve_dotted(
    target: str,
) -> tuple[ModuleType, list[str] | None]:
    parts = target.split('.')
    first_error: ModuleNotFoundError | None = None

    # Try each prefix from longest to shortest.
    for prefix_length in range(len(parts), 0, -1):
        head = '.'.join(parts[:prefix_length])
        tail_parts = parts[prefix_length:]
        try:
            module = importlib.import_module(head)
        except ModuleNotFoundError as exc:
            if not _is_missing_prefix_error(exc, head):
                # The prefix exists but raised inside its own
                # imports — propagate rather than mask as a bad
                # selector.
                raise
            if first_error is None:
                first_error = exc
            continue
        if not tail_parts:
            return module, None
        if len(tail_parts) > 2:
            raise LookupError(
                f'cannot resolve {target!r}: too many trailing '
                f'segments after module {head!r}'
            )
        return module, ['.'.join(tail_parts)]

    # No prefix imported. Re-raise the natural error.
    assert first_error is not None
    raise first_error


def _is_missing_prefix_error(
    exc: ModuleNotFoundError,
    head: str,
) -> bool:
    # The prefix itself is what's missing, vs an unrelated import
    # inside the prefix's module.
    return exc.name is not None and (
        exc.name == head or head.startswith(exc.name + '.')
    )
