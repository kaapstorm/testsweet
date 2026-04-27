import importlib
import importlib.util
import pathlib
import sys
from types import ModuleType


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
    info = _dotted_name_for_path(path)
    if info is None:
        return _exec_module_from_path(path)
    dotted, rootdir = info
    rootdir_str = str(rootdir)
    if rootdir_str not in sys.path:
        sys.path.insert(0, rootdir_str)
    return importlib.import_module(dotted)


def _dotted_name_for_path(
    path: pathlib.Path,
) -> tuple[str, pathlib.Path] | None:
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
        # Loose file; caller falls back to spec_from_file_location.
        return None
    return '.'.join(parts), parent
