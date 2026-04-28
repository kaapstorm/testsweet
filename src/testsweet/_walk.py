import fnmatch
import os
import pathlib

from testsweet._config import DiscoveryConfig


_EXCLUDED_DIR_NAMES = frozenset({'__pycache__', 'node_modules'})


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
