import importlib
import importlib.util
import pathlib
from types import ModuleType


def parse_target(
    target: str,
) -> tuple[ModuleType, list[str] | None]:
    if '/' in target or target.endswith('.py'):
        return _load_path(target), None
    return _resolve_dotted(target)


def _load_path(target: str) -> ModuleType:
    path = pathlib.Path(target).resolve()
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise ImportError(f'cannot load {target!r} from path')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _resolve_dotted(
    target: str,
) -> tuple[ModuleType, list[str] | None]:
    parts = target.split('.')
    # Walk from longest prefix to shortest. The first attempt is the
    # full string; on success, no selector tail.
    head_parts = list(parts)
    tail_parts: list[str] = []
    first_error: ModuleNotFoundError | None = None
    while head_parts:
        head = '.'.join(head_parts)
        try:
            module = importlib.import_module(head)
        except ModuleNotFoundError as exc:
            # Distinguish "head itself doesn't exist" from "head
            # exists but raised ModuleNotFoundError on an internal
            # import". exc.name is the missing dotted name; if it
            # isn't head or a prefix of head, the failure came from
            # inside a module we did manage to start importing —
            # propagate rather than masking it as a bad selector.
            if exc.name is None or not (
                exc.name == head or head.startswith(exc.name + '.')
            ):
                raise
            if first_error is None:
                first_error = exc
            tail_parts.insert(0, head_parts.pop())
            continue
        if not tail_parts:
            return module, None
        if len(tail_parts) > 2:
            raise LookupError(
                f'cannot resolve {target!r}: too many trailing '
                f'segments after module {head!r}'
            )
        return module, ['.'.join(tail_parts)]
    assert first_error is not None
    raise first_error
