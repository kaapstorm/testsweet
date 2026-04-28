import pathlib
from types import ModuleType

from testsweet._classify import _resolve_dotted
from testsweet._config import DiscoveryConfig
from testsweet._loaders import _load_path, _load_path_for_walk
from testsweet._walk import (
    _build_exclude_set,
    _resolve_include_paths,
    _walk_directory,
)


# A discovered test unit: a module, plus an optional list of selectors
# (dotted-name tails like 'Foo.bar') narrowing what to run within it.
# `None` means "run everything in this module".
TargetGroup = tuple[ModuleType, list[str] | None]


def discover_targets(
    argv: list[str],
    config: DiscoveryConfig,
) -> list[TargetGroup]:
    excluded = _build_exclude_set(config)
    raw: list[TargetGroup] = []
    if not argv:
        raw.extend(_bare_invocation(config, excluded))
    else:
        for arg in argv:
            raw.extend(parse_target(arg, config, excluded))

    # Group by module identity, preserving first-seen order via dict
    # insertion order. Whole-module entries (names is None) win over
    # selectors for the same module.
    #
    # Keying by id(module) is safe because `raw` holds a strong
    # reference to every module for the duration of the loop — id()
    # is only guaranteed unique among live objects.
    by_id: dict[int, TargetGroup] = {}
    for module, names in raw:
        key = id(module)
        existing = by_id.get(key)
        if existing is None:
            by_id[key] = (module, names)
            continue
        _, existing_names = existing
        if existing_names is None or names is None:
            by_id[key] = (module, None)
        else:
            by_id[key] = (module, existing_names + names)
    return list(by_id.values())


def parse_target(
    target: str,
    config: DiscoveryConfig | None = None,
    excluded: set[pathlib.Path] | None = None,
) -> list[TargetGroup]:
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


def _bare_invocation(
    config: DiscoveryConfig,
    excluded: set[pathlib.Path],
) -> list[TargetGroup]:
    roots = _resolve_include_paths(config)
    if not roots:
        roots = [pathlib.Path('.').resolve()]
    out: list[TargetGroup] = []
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
