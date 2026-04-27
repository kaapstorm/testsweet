# Design: pyproject.toml discovery configuration

## Scope

Add a `[tool.assertions.discovery]` section to `pyproject.toml` that
narrows the default match-all-`*.py` discovery behavior. The schema:

```toml
[tool.assertions.discovery]
include_paths = ["tests/**", "src/**/tests/**"]
exclude_paths = ["src/vendored/**"]
test_files = ["test_*.py", "*_tests.py"]
```

In scope:

- Locating `pyproject.toml` by walking up from cwd.
- Parsing the three keys and validating them.
- Applying the filters during directory walks.
- Cleanup: refactor `_walk_directory` to use `os.scandir`; extract a
  shared loader helper consolidating the duplicated
  `spec_from_file_location` paths in `_load_path` and
  `_load_path_for_walk`.

Out of scope:

- `use_grep` and grep-prefilter implementation (slice B.3).
- Configurable directory exclusions (the built-in hidden /
  `__pycache__` / `node_modules` set stays hard-coded).
- Per-target overrides on the command line.
- Globbing inside dotted-name selectors (`module.foo.*`).

## Approach

A new helper module `_config.py` finds `pyproject.toml` and returns a
parsed `DiscoveryConfig` dataclass with the three lists. `parse_target`
consults the config when classifying a directory walk. The CLI loads
the config once at the start of `main` and passes it to each
directory-walking call.

When no `pyproject.toml` is found, or the file has no
`[tool.assertions.discovery]` table, the config is empty (all three
lists empty) and current behavior is preserved.

## Public surface

```python
from assertions._config import DiscoveryConfig, load_config


@dataclass(frozen=True)
class DiscoveryConfig:
    include_paths: tuple[str, ...] = ()
    exclude_paths: tuple[str, ...] = ()
    test_files: tuple[str, ...] = ()
    project_root: pathlib.Path | None = None


def load_config(start: pathlib.Path) -> DiscoveryConfig: ...
```

`load_config(start)` walks up from `start` until it finds a
`pyproject.toml`, parses it, and returns a `DiscoveryConfig`. If none
is found, returns the default empty config (with `project_root=None`).

## Behavior

### Locating `pyproject.toml`

Walk up from `start` (the cwd at the moment `main` runs):

1. If `start / 'pyproject.toml'` exists, that's it.
2. Else move to `start.parent` and try again.
3. Stop at the filesystem root. If nothing found, return the default
   empty config with `project_root=None`.

`project_root` is the directory containing the discovered
`pyproject.toml`.

### Parsing the table

Use `tomllib` (stdlib in Python 3.11+). Read
`[tool.assertions.discovery]`. Each of the three keys is optional;
missing keys yield empty tuples.

Validation rules:

- Each value must be a list of strings. A non-list, or a list
  containing non-strings, raises
  `ConfigurationError(f'tool.assertions.discovery.{key} must be a list
  of strings')`. The `ConfigurationError` is a new exception class in
  `_config.py`, subclassing `Exception`.
- Unknown keys under `[tool.assertions.discovery]` raise
  `ConfigurationError(f'unknown key {key!r} in
  [tool.assertions.discovery]')`. Strict-by-default catches typos.

### Applying filters during a directory walk

The walk function gains a `config` parameter:

```python
def _walk_directory(
    root: pathlib.Path,
    config: DiscoveryConfig,
) -> list[pathlib.Path]:
    ...
```

Behavior:

1. Start with the existing behavior: depth-first, alphabetical, with
   built-in directory exclusions (hidden, `__pycache__`,
   `node_modules`).
2. For each `*.py` file collected:
   - If `config.test_files` is non-empty, the file's `.name` must
     match at least one pattern (using `fnmatch.fnmatch`).
   - If `config.exclude_paths` is non-empty, drop the file if its
     resolved absolute path is in a pre-computed exclude set (see
     below).
3. Return the filtered list, in the same alphabetical order.

#### Exclude set pre-computation

`pathlib.PurePath.match` on Python 3.11 does NOT support `**`, which
makes per-file matching of patterns like `src/vendored/**` unreliable.
Instead, the implementation expands each `exclude_paths` pattern via
`project_root.glob(pattern)` once at the start of the run, collecting
every matched file into a `set[pathlib.Path]` of resolved absolute
paths. The walk's filter step is then a simple set membership check.

This is computed once per `main()` invocation, in the same place the
config is loaded. Pseudo-code:

```python
def _build_exclude_set(
    config: DiscoveryConfig,
) -> set[pathlib.Path]:
    if not config.exclude_paths or config.project_root is None:
        return set()
    excluded: set[pathlib.Path] = set()
    for pattern in config.exclude_paths:
        for match in config.project_root.glob(pattern):
            if match.is_file():
                excluded.add(match.resolve())
            elif match.is_dir():
                for sub in match.rglob('*.py'):
                    excluded.add(sub.resolve())
    return excluded
```

Trade-off: glob expansion walks the matching subtree once. For large
trees with broad exclude patterns this is real work, but it happens
once before the main walk; subsequent per-file checks are O(1)
membership tests. B.3's grep prefilter is the longer-term answer for
huge trees.

Note: include_paths is NOT applied per-file inside `_walk_directory`.
It's applied at the level of "what root(s) do we walk in the first
place" (next section).

### `include_paths` and target dispatch

The bare-invocation case (`python -m assertions` with no args) used to
default to walking cwd. With config:

- If `config.include_paths` is empty, walk cwd (today's behavior).
- If `config.include_paths` is non-empty, walk each path in the list,
  resolved relative to `config.project_root`. If the same `.py` file
  is reachable from more than one include path (e.g., overlapping
  globs), it appears once — `parse_target`'s grouping by module
  identity already handles the dedup at the `__main__.py` level.

`include_paths` entries are glob patterns. They can match directories
(in which case the walk recurses into them) or files directly. The
implementation uses `pathlib.Path.glob` from the project root for each
pattern; for each match that is a directory, recurse via
`_walk_directory`; for each match that is a file ending in `.py`,
include it directly.

Concretely, for the bare case:

```python
def _resolve_include_paths(
    config: DiscoveryConfig,
) -> list[pathlib.Path]:
    if not config.include_paths:
        return [pathlib.Path('.').resolve()]
    assert config.project_root is not None
    out: list[pathlib.Path] = []
    for pattern in config.include_paths:
        for match in config.project_root.glob(pattern):
            out.append(match)
    return out
```

The walker then handles each match: if it's a directory, walk it; if
it's a file, include it as-is.

### Argv directory targets

When the user passes a directory target on argv (`python -m assertions
tests/`), the user's explicit intent wins:

- `include_paths` is **not** applied — the user told us where to look.
- `exclude_paths` and `test_files` ARE applied within that walk.
  Otherwise a user would have to disable both keys in pyproject.toml
  to get a "run everything in this dir" behavior, which is wrong:
  excludes for `vendored/` should still skip vendored even when the
  walk root is `src/`.

### Argv file targets and dotted modules

These are unchanged. The user named a single file or module
explicitly; filters don't apply.

### Cleanup: `_walk_directory` to `os.scandir`

Replace the current implementation, which does
`for name in sorted(os.listdir(...))` with `os.scandir`-based
recursion. `os.scandir` returns `DirEntry` objects with cached
`is_dir()` / `is_file()`, avoiding a `stat` per entry. Symlinks are
not followed (`is_dir(follow_symlinks=False)`); we'll address symlink
loops in B.3 if needed.

The interface stays the same — same return shape, same alphabetical
order, same exclusion rules.

### Cleanup: shared loader helper

Currently `_load_path` and the fallback branch of `_load_path_for_walk`
contain the same four lines:

```python
spec = importlib.util.spec_from_file_location(stem, path)
if spec is None or spec.loader is None:
    raise ImportError(...)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
return module
```

Extract to `_exec_module_from_path(path: pathlib.Path) -> ModuleType`
in `_targets.py`. Both `_load_path` and `_load_path_for_walk`'s
fallback call it.

## Module layout

| File | Action | Purpose |
|------|--------|---------|
| `src/assertions/_config.py` | create | `DiscoveryConfig`, `ConfigurationError`, `load_config` |
| `src/assertions/_targets.py` | modify | `parse_target` and `_walk_directory` accept config; `os.scandir`; `_exec_module_from_path` helper |
| `src/assertions/__main__.py` | modify | Load config once at start of `main`; pass to dispatch |
| `src/assertions/__init__.py` | modify | Re-export `ConfigurationError` (so users can catch it) |

## Tests

### `tests/test_config.py` (new)

1. `load_config` returns the default empty config when no
   `pyproject.toml` is found anywhere up the tree.
2. `load_config` parses a `pyproject.toml` containing only
   `[tool.assertions.discovery]` and returns a populated config.
3. `load_config` walks up from a subdirectory and finds the pyproject
   in an ancestor.
4. A pyproject without `[tool.assertions.discovery]` returns the
   empty config (but `project_root` is set).
5. A non-list value for any of the three keys raises
   `ConfigurationError`.
6. An unknown key under `[tool.assertions.discovery]` raises
   `ConfigurationError`.
7. `project_root` is the directory containing the found pyproject.

### `tests/test_targets.py` (modify, additions)

8. `_walk_directory` with a config that has `exclude_paths` set drops
   matching files.
9. `_walk_directory` with `test_files` set keeps only matching names.
10. `_walk_directory` with both set ANDs the filters.
11. `_walk_directory` with empty config has identical behavior to the
    no-config case (regression).
12. `_walk_directory` after the `os.scandir` refactor produces the
    same alphabetical, depth-first order as before (existing tests
    must keep passing).
13. `_exec_module_from_path` loads a `.py` file and returns the
    module object — direct unit test that the extracted helper is
    the integration point for both loader paths.

### `tests/test_cli.py` (modify, additions)

14. With a `pyproject.toml` setting `include_paths = ["sub/"]`, a
    bare invocation walks only `sub/`, not the rest of the tmpdir.
15. With `exclude_paths = ["vendored/**"]`, a bare invocation skips
    files under `vendored/`.
16. With `test_files = ["test_*.py"]`, a bare invocation skips files
    whose names don't match (e.g., a file named `helper.py` even if
    it has `@test`-decorated functions).
17. Passing a directory on argv ignores `include_paths` but still
    honors `exclude_paths` and `test_files`.

### Test isolation note

The `tests/test_config.py` tests build pyproject content inside
`tempfile.TemporaryDirectory` and pass an explicit `start` path to
`load_config`, so they don't depend on the project's own
pyproject.toml. CLI tests that need a config use `cwd=` on the
`subprocess.run` invocation so the walk-up finds the tmpdir's
pyproject, not the repo's.

## Acceptance

- `load_config` handles present/absent/partial pyproject correctly
  and raises `ConfigurationError` on schema violations.
- A bare invocation in a tmpdir with config respects `include_paths`,
  `exclude_paths`, and `test_files`.
- All previous tests still pass.
- `uv run mypy` reports no issues.
