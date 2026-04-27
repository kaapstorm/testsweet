# Design: extract `discover_targets` as the CLI/discovery seam

## Scope

Replace the implicit boundary between `__main__.py` and the discovery
machinery (currently five private imports across three modules) with
a single public-internal function `discover_targets(argv, config)` in
`_targets.py`. Move the helpers that only the CLI calls
(`_bare_invocation`, `_add_to_groups`) alongside it.

In scope:

- Add `discover_targets` to `_targets.py`.
- Move `_bare_invocation` and `_add_to_groups` from `__main__.py` to
  `_targets.py`.
- Reduce `__main__.py` imports to three: `_config.load_config`,
  `_runner.run`, `_targets.discover_targets`.
- Add direct unit tests for `discover_targets` (`tests/test_targets.py`).

Out of scope:

- Behavior change. Same units run, same output, same exit codes.
- Splitting `discover_targets` into a new `_discovery.py` module
  (the existing `_targets.py` already names the responsibility).
- Renaming `parse_target` (still a useful per-target helper).
- Refactoring the CLI's print loop (two lines, fine inline).
- Runner cleanup (point #3 of the post-merge review).

## Approach

Today's `main()` does:

1. Load config.
2. Build exclude set.
3. Resolve argv (or bare-invocation roots) into a list of
   `(module, names)` pairs.
4. Merge by module identity.
5. Run, print, exit.

Steps 1, 2, 3, 4 are "discovery" — they answer "what should we run".
Step 5 is "execution" — print results, set exit code. Today the
distinction is hidden behind five private imports; this slice surfaces
it as a function.

## Public surface

```python
from assertions._targets import discover_targets


def discover_targets(
    argv: list[str],
    config: DiscoveryConfig,
) -> list[tuple[ModuleType, list[str] | None]]:
    """Resolve argv (or bare-invocation roots from config) into the
    list of (module, names) pairs the runner should process. Merges
    duplicate modules; whole-module entries win over selectors."""
```

`__main__.py`'s entire interaction with discovery becomes one call:

```python
groups = discover_targets(argv, config)
for module, names in groups:
    for name, exc in run(module, names=names):
        ...
```

## Behavior

### `discover_targets(argv, config)`

```python
def discover_targets(
    argv: list[str],
    config: DiscoveryConfig,
) -> list[tuple[ModuleType, list[str] | None]]:
    excluded = _build_exclude_set(config)
    raw: list[tuple[ModuleType, list[str] | None]] = []
    if not argv:
        raw.extend(_bare_invocation(config, excluded))
    else:
        for arg in argv:
            raw.extend(parse_target(arg, config, excluded))
    groups: list[tuple[ModuleType, list[str] | None]] = []
    for module, names in raw:
        _add_to_groups(groups, module, names)
    return groups
```

Properties:

- Bare invocation (`argv == []`) defers to `_bare_invocation`, which
  consults `config.include_paths` (resolving via `_resolve_include_paths`)
  or defaults to cwd.
- argv with one or more targets: each is resolved through
  `parse_target` (existing behavior).
- Output is deduped by module identity. If the same module is
  produced more than once (e.g., the user wrote
  `python -m assertions some.mod some.mod.foo`), the first
  whole-module entry wins, and subsequent selectors for the same
  module are absorbed (existing semantics from `_add_to_groups`).
- The order of groups follows argv order of first appearance per
  module (existing semantics).

### `_bare_invocation(config, excluded)` (moved verbatim from `__main__.py`)

Unchanged signature and behavior:

```python
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
```

### `_add_to_groups(groups, module, names)` (moved verbatim)

Unchanged.

### `__main__.py` after the move

```python
import pathlib
import sys

from assertions._config import load_config
from assertions._runner import run
from assertions._targets import discover_targets


USAGE = 'usage: python -m assertions [<target>...]'


def main(argv: list[str]) -> int:
    saved_sys_path = list(sys.path)
    try:
        config = load_config(pathlib.Path.cwd())
        groups = discover_targets(argv, config)
        failed = False
        for module, names in groups:
            for name, exc in run(module, names=names):
                if exc is None:
                    print(f'{name} ... ok')
                else:
                    print(
                        f'{name} ... FAIL: {type(exc).__name__}: {exc}'
                    )
                    failed = True
        return 1 if failed else 0
    finally:
        sys.path[:] = saved_sys_path


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
```

About 25 lines. Three imports — all `from assertions._<module> import
<symbol>`, none reaching past the named entry point. `USAGE` lingers
as a constant even though no path inside `main` prints it; it's kept
for any future "show usage" pathway and to keep this slice scoped to
the boundary fix. (Removing `USAGE` is a one-line cleanup that can
land in a follow-up.)

### Imports — before vs after

Before (5 names from 3 modules):
```python
from assertions._loaders import _load_path_for_walk
from assertions._targets import parse_target
from assertions._walk import (
    _build_exclude_set,
    _resolve_include_paths,
    _walk_directory,
)
```

After (3 names from 3 modules):
```python
from assertions._config import load_config
from assertions._runner import run
from assertions._targets import discover_targets
```

## Module layout

| File | Action | Purpose |
|------|--------|---------|
| `src/assertions/_targets.py` | modify | Add `discover_targets`, `_bare_invocation`, `_add_to_groups` |
| `src/assertions/__main__.py` | modify | Call `discover_targets`; drop direct imports of `_walk`/`_loaders` helpers |

No new files, no deletions.

## Tests

### `tests/test_targets.py` (additions)

A new `TestDiscoverTargets` class exercising the function directly.
Each test builds a `DiscoveryConfig` (sometimes with a
`pyproject.toml` in a `tempfile.TemporaryDirectory`) and calls
`discover_targets(argv, config)`.

1. Bare invocation with no `include_paths` → walks cwd. Use
   `monkeypatch`-equivalent (a `tempfile.TemporaryDirectory` and
   `os.chdir` inside a `try/finally`, or use `pathlib.Path.cwd`
   indirection — see implementation note below) to point cwd at a
   tmp tree with one `.py` test file; assert one entry returned.
2. Bare invocation with `include_paths` → walks those paths
   relative to `config.project_root`, ignoring cwd.
3. argv with a single dotted module → returns that module with
   `names=None`.
4. argv with a single dotted selector
   (`module.Class.method`) → returns the parent module with the
   tail in `names`.
5. argv with two different dotted modules → both appear in
   group order.
6. argv with the same module appearing twice (`some.mod some.mod`)
   → returned once (deduped); `names` is `None` (whole-module).
7. argv with whole-module followed by a selector for the same
   module (`some.mod some.mod.foo`) → returned once; `names` is
   `None` (whole-module wins).
8. argv with two selectors against the same module → returned
   once; `names` is the merged list.
9. argv with a directory target → walks the directory; entries
   reflect the `_walk_directory` contract (test_files filtering,
   exclusion).

**Implementation note on cwd-handling tests:** `discover_targets`
doesn't take a cwd parameter directly; bare invocation defaults to
`pathlib.Path('.').resolve()` inside `_bare_invocation`. To test
without `os.chdir` (which mutates global state), the bare-invocation
tests can instead use a config with explicit `include_paths` (test 2)
since that path bypasses cwd. Test 1 ("walks cwd") uses an
`os.chdir` save/restore pattern; it's the one place cwd matters.

### `tests/test_cli.py`

Unchanged. The CLI's behavior is identical, and existing CLI tests
already exercise the end-to-end path through `discover_targets`.

### Tests already in `tests/test_targets.py`

`TestParseTarget` and `TestParseTargetDirectory` continue to test
`parse_target` directly. `discover_targets` wraps `parse_target`, so
its tests don't duplicate that coverage — they focus on the new
behaviors (merging, bare-invocation routing).

## Acceptance

- `__main__.py` imports exactly: `pathlib`, `sys`,
  `assertions._config.load_config`, `assertions._runner.run`,
  `assertions._targets.discover_targets`.
- `discover_targets` is the only entry point from CLI into discovery.
- All previous tests pass.
- The new `TestDiscoverTargets` tests pass (9 tests).
- `uv run mypy` reports no issues.
- The CLI's behavior is unchanged for every existing scenario:
  bare, single argv, multiple argv, file path, directory, dotted
  module, dotted selector, mixed, unmatched selector.
