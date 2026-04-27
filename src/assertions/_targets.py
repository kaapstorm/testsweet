import fnmatch
import importlib
import importlib.util
import os
import pathlib
import sys
from types import ModuleType

from assertions._config import DiscoveryConfig


_EXCLUDED_DIR_NAMES = frozenset({'__pycache__', 'node_modules'})


def parse_target(
    target: str,
    config: DiscoveryConfig | None = None,
    excluded: set[pathlib.Path] | None = None,
) -> list[tuple[ModuleType, list[str] | None]]:
    if (
        '/' in target
        or target.endswith('.py')
        or pathlib.Path(target).is_dir()
    ):
        path = pathlib.Path(target).resolve()
        if path.is_dir():
            return [
                (_load_path_for_walk(p), None)
                for p in _walk_directory(
                    path,
                    config=config,
                    excluded=excluded,
                )
            ]
        return [(_load_path(target), None)]
    return [_resolve_dotted(target)]


def _resolve_include_paths(
    config: DiscoveryConfig,
) -> list[pathlib.Path]:
    if not config.include_paths or config.project_root is None:
        return []
    out: list[pathlib.Path] = []
    for pattern in config.include_paths:
        for match in config.project_root.glob(pattern):
            out.append(match)
    return out


def _build_exclude_set(
    config: DiscoveryConfig,
) -> set[pathlib.Path]:
    # Glob each exclude pattern and add every match (file or
    # directory) directly. The walker checks each entry against this
    # set before recursing, so an excluded directory prunes its whole
    # subtree without us having to walk into it here.
    if not config.exclude_paths or config.project_root is None:
        return set()
    excluded: set[pathlib.Path] = set()
    for pattern in config.exclude_paths:
        for match in config.project_root.glob(pattern):
            excluded.add(match.resolve())
    return excluded


def _exec_module_from_path(path: pathlib.Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise ImportError(f'cannot load {path} as a module')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_path(target: str) -> ModuleType:
    return _exec_module_from_path(pathlib.Path(target).resolve())


def _load_path_for_walk(path: pathlib.Path) -> ModuleType:
    dotted, rootdir = _dotted_name_for_path(path)
    if dotted is not None and rootdir is not None:
        rootdir_str = str(rootdir)
        if rootdir_str not in sys.path:
            sys.path.insert(0, rootdir_str)
        return importlib.import_module(dotted)
    return _exec_module_from_path(path)


def _walk_directory(
    root: pathlib.Path,
    config: DiscoveryConfig | None = None,
    excluded: set[pathlib.Path] | None = None,
) -> list[pathlib.Path]:
    # Symlinks (both directory and file) are not followed: we only
    # consider entries that are real files / real directories. This
    # avoids cycles and prevents picking up source files outside the
    # walked tree. A test file deliberately reached via a symlink
    # will not be discovered — the user must pass it as an explicit
    # target, or set up `__init__.py` to make it a real package
    # module.
    out: list[pathlib.Path] = []
    with os.scandir(root) as it:
        entries = sorted(it, key=lambda e: e.name)
    for entry in entries:
        entry_path = pathlib.Path(entry.path)
        if excluded is not None and entry_path.resolve() in excluded:
            continue
        if entry.is_dir(follow_symlinks=False):
            if _is_excluded_dir(entry.name):
                continue
            out.extend(
                _walk_directory(
                    entry_path,
                    config=config,
                    excluded=excluded,
                )
            )
        elif entry.is_file(follow_symlinks=False) and entry.name.endswith(
            '.py'
        ):
            if not _accepts_file(entry_path, config, excluded):
                continue
            out.append(entry_path)
    return out


def _accepts_file(
    path: pathlib.Path,
    config: DiscoveryConfig | None,
    excluded: set[pathlib.Path] | None,
) -> bool:
    if excluded is not None and path.resolve() in excluded:
        return False
    if config is not None and config.test_files:
        if not any(
            fnmatch.fnmatch(path.name, pattern)
            for pattern in config.test_files
        ):
            return False
    return True


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
