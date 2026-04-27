import pathlib
import sys
from types import ModuleType

from assertions._config import DiscoveryConfig, load_config
from assertions._runner import run
from assertions._loaders import _load_path_for_walk
from assertions._targets import (
    _build_exclude_set,
    _resolve_include_paths,
    _walk_directory,
    parse_target,
)


USAGE = 'usage: python -m assertions [<target>...]'


def main(argv: list[str]) -> int:
    saved_sys_path = list(sys.path)
    try:
        config = load_config(pathlib.Path.cwd())
        excluded = _build_exclude_set(config)
        if not argv:
            argv_groups = _bare_invocation(config, excluded)
        else:
            argv_groups = []
            for arg in argv:
                argv_groups.extend(parse_target(arg, config, excluded))
        groups: list[tuple[ModuleType, list[str] | None]] = []
        for module, names in argv_groups:
            _add_to_groups(groups, module, names)
        failed = False
        for module, merged_names in groups:
            results = run(module, names=merged_names)
            for name, exc in results:
                if exc is None:
                    print(f'{name} ... ok')
                else:
                    print(f'{name} ... FAIL: {type(exc).__name__}: {exc}')
                    failed = True
        return 1 if failed else 0
    finally:
        sys.path[:] = saved_sys_path


def _bare_invocation(
    config: DiscoveryConfig,
    excluded: set[pathlib.Path],
) -> list[tuple[ModuleType, list[str] | None]]:
    roots = _resolve_include_paths(config)
    if not roots:
        roots = [pathlib.Path('.').resolve()]
    out: list[tuple[ModuleType, list[str] | None]] = []
    for root in roots:
        if root.is_file() and root.suffix == '.py':
            out.append((_load_path_for_walk(root), None))
        elif root.is_dir():
            for path in _walk_directory(
                root,
                config=config,
                excluded=excluded,
            ):
                out.append((_load_path_for_walk(path), None))
    return out


def _add_to_groups(
    groups: list[tuple[ModuleType, list[str] | None]],
    module: ModuleType,
    names: list[str] | None,
) -> None:
    for i, (existing_module, existing_names) in enumerate(groups):
        if existing_module is module:
            if existing_names is None or names is None:
                groups[i] = (module, None)
            else:
                groups[i] = (module, existing_names + names)
            return
    groups.append((module, names))


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
