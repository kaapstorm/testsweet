import importlib
import importlib.util
import os
import pathlib
import sys
from types import ModuleType


_EXCLUDED_DIR_NAMES = frozenset({'__pycache__', 'node_modules'})


def parse_target(
    target: str,
) -> list[tuple[ModuleType, list[str] | None]]:
    if (
        '/' in target
        or target.endswith('.py')
        or pathlib.Path(target).is_dir()
    ):
        path = pathlib.Path(target).resolve()
        if path.is_dir():
            return [
                (_load_path_for_walk(p), None) for p in _walk_directory(path)
            ]
        return [(_load_path(target), None)]
    return [_resolve_dotted(target)]


def _load_path(target: str) -> ModuleType:
    path = pathlib.Path(target).resolve()
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise ImportError(f'cannot load {target!r} from path')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_path_for_walk(path: pathlib.Path) -> ModuleType:
    dotted, rootdir = _dotted_name_for_path(path)
    if dotted is not None and rootdir is not None:
        rootdir_str = str(rootdir)
        if rootdir_str not in sys.path:
            sys.path.insert(0, rootdir_str)
        return importlib.import_module(dotted)
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise ImportError(f'cannot load {path} from walk')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _walk_directory(root: pathlib.Path) -> list[pathlib.Path]:
    out: list[pathlib.Path] = []
    for name in sorted(os.listdir(root)):
        entry = root / name
        if entry.is_dir():
            if _is_excluded_dir(name):
                continue
            out.extend(_walk_directory(entry))
        elif name.endswith('.py'):
            out.append(entry)
    return out


def _is_excluded_dir(name: str) -> bool:
    if name.startswith('.'):
        return True
    return name in _EXCLUDED_DIR_NAMES


def _dotted_name_for_path(
    path: pathlib.Path,
) -> tuple[str | None, pathlib.Path | None]:
    # Walk up while __init__.py is present; collect names. The
    # rootdir is the first ancestor that does NOT contain
    # __init__.py.
    parts: list[str] = [path.stem]
    parent = path.parent
    while (parent / '__init__.py').exists():
        parts.insert(0, parent.name)
        if parent.parent == parent:
            break
        parent = parent.parent
    if len(parts) == 1:
        # No package chain; loose file. Caller falls back to
        # spec_from_file_location.
        return None, None
    return '.'.join(parts), parent


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
