# Design: bare auto-discovery + directory arguments

## Scope

Allow `python -m assertions` with no arguments (walk cwd) and with a
directory argument (walk that directory). Discovered tests run via
the existing `run(module)` machinery.

In scope:

- Bare `python -m assertions` → walk current working directory.
- Directory target: `python -m assertions tests/` → walk that
  directory.
- Default file pattern: every `*.py` file.
- Built-in directory exclusions: any name starting with `.`
  (`.git`, `.venv`, etc.), `__pycache__`, `node_modules`.
- Package-aware import for files inside an `__init__.py` chain;
  fallback to `spec_from_file_location` for loose files.
- `sys.path` snapshot + restore around the whole run.
- Import errors from a discovered file propagate; the run aborts.

Out of scope (slice B.2 and beyond):

- `pyproject.toml` configuration (path filters, prefix/suffix/dirname
  narrowing).
- Multiple-pattern matching beyond all `*.py` files.
- Configurable directory exclusions.
- Caching, parallelism, watch mode.
- Conftest-style hooks.

## Approach

Add a directory branch to `parse_target`. Walk the directory tree,
build a list of `.py` files, compute each file's dotted name (or
fall back to a stem-named module), and return one
`(module, names=None)` entry per file.

`parse_target`'s return type widens from a single tuple to a list of
tuples — a single-file or single-module target returns a one-element
list; a directory target returns N elements. The CLI iterates and
groups by module identity (existing logic from slice A).

The CLI's "no args" case becomes `argv = ['.']` at the top of
`main` — no other special-casing.

`sys.path` is snapshotted at the start of each `python -m assertions`
run and restored at the end, including on exception. Modules added to
`sys.modules` during the run are NOT removed; that's standard Python.

## Public surface

```
python -m assertions                 # walks cwd
python -m assertions tests/          # walks tests/
python -m assertions tests/ src/     # walks both
python -m assertions tests/ pkg.mod  # mix dir + dotted module
python -m assertions tests/foo.py    # still works (file path, slice A)
```

`parse_target` becomes:

```python
def parse_target(
    target: str,
) -> list[tuple[ModuleType, list[str] | None]]:
    ...
```

A single-file or single-module target returns a one-element list.

## Behavior

### Target classification (extends slice A)

In order:

1. **Path-like** (`'/' in target` OR `target.endswith('.py')`):
   resolve via `pathlib.Path(target).resolve()`. Then:
   - If the resolved path is a directory → walk it, yield N entries.
   - If it's a file → load via `spec_from_file_location` (slice A
     behavior); yield one entry.
   - Otherwise → propagate `FileNotFoundError`.
2. **Dotted target**: longest-importable-prefix resolution from
   slice A; yield one entry.

### Directory walk

Inputs: a directory path. Outputs: a list of `(file_path,
dotted_name_or_None)` tuples, in deterministic order.

```python
def _walk_directory(root: pathlib.Path) -> list[pathlib.Path]:
    out: list[pathlib.Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        # Prune excluded dirs in place; sort for determinism.
        dirnames[:] = sorted(
            d for d in dirnames
            if not _is_excluded_dir(d)
        )
        for name in sorted(filenames):
            if name.endswith('.py'):
                out.append(pathlib.Path(dirpath) / name)
    return out


def _is_excluded_dir(name: str) -> bool:
    if name.startswith('.'):
        return True
    return name in {'__pycache__', 'node_modules'}
```

Order: depth-first, alphabetical within each level. Stable across
runs.

If the directory has no `.py` files anywhere: walking returns `[]`;
`parse_target` returns `[]`; the CLI runs nothing and exits 0.

### Package-aware import

For each `.py` file path:

1. Walk up from `path.parent`, collecting directory names while each
   directory contains an `__init__.py`. Stop at the first directory
   that does NOT contain one.
2. The collected names (reversed) plus the file's stem form the
   dotted name. Example:
   - File: `/repo/tests/fixtures/runner/test_foo.py`
   - `runner/` has `__init__.py`, `fixtures/` has `__init__.py`,
     `tests/` has `__init__.py`, `/repo/` does not.
   - Dotted name: `tests.fixtures.runner.test_foo`. Rootdir: `/repo/`.
3. Add the rootdir to `sys.path` if not already present (insert at
   index 0).
4. `importlib.import_module(dotted_name)`.
5. If step 2 yields an empty chain (the file's parent has no
   `__init__.py`): fall back to
   `importlib.util.spec_from_file_location(path.stem, path)` and
   `module_from_spec` + `spec.loader.exec_module`. This is the same
   path used by the file-path target form.

**Known limitation:** two loose files named `foo.py` in different
directories collide on `sys.modules['foo']` if they're both
discovered. The first one wins; the second binding overwrites it
(per `module_from_spec`'s default behavior). Users who hit this can
add `__init__.py` files to put the loose modules in distinct
packages. Documented; not addressed in this slice.

### `sys.path` snapshot + restore

The CLI's `main` snapshots `sys.path` before any `parse_target` call
and restores it in a `finally` block:

```python
def main(argv: list[str]) -> int:
    if not argv:
        argv = ['.']
    saved_sys_path = list(sys.path)
    try:
        # ... existing CLI logic ...
        return ...
    finally:
        sys.path[:] = saved_sys_path
```

Modules imported during the run remain in `sys.modules`. That matches
how `unittest` and `pytest` operate.

### Errors

- Directory does not exist: `FileNotFoundError` propagates from
  `pathlib.Path.resolve()` (when `strict=True`) or from the first
  `os.walk` iteration. Either way, traceback to user.
- Discovered file fails to import (syntax error, missing dep):
  exception propagates. The run aborts at that file. Other discovered
  files do not run. Consistent with slice A's "internal import error
  propagates" rule.
- Discovered file imports cleanly but its tests raise: handled by
  `run` as today (failures recorded, run continues for that module).

### Defaults at the CLI level

- 0 args: `argv = ['.']`.
- Usage line: `usage: python -m assertions [<target>...]` (target
  becomes optional).

## Module layout

| File | Action | Purpose |
|------|--------|---------|
| `src/assertions/_targets.py` | modify | Add `_walk_directory`, `_dotted_name_for_path`, `_load_path_or_walk`; widen `parse_target` return type |
| `src/assertions/__main__.py` | modify | Default to `['.']` when argv empty; iterate the now-list `parse_target` result; snapshot+restore `sys.path` |

No new module — the walker fits in `_targets.py`. If slice B.2 grows
the discovery surface, we'll split.

## Tests

### `tests/test_targets.py` (modify)

Existing tests need a small update because `parse_target` now returns
a list. Update each existing test to read `result[0]` (it's a
single-target return → one-element list).

New tests:

1. `parse_target('tests/fixtures/runner/')` returns a non-empty list;
   every entry's `names` is `None`; modules are sorted by full path.
2. Each discovered module's identity matches `import_module(<dotted
   name>)` for the same file.
3. `parse_target('tests/fixtures/runner/')` skips a hidden directory
   placed inside (write a `.tmp/` directory with a `.py` file as a
   tmp setup, then resolve and walk; assert no entry whose path is
   under `.tmp/`).
4. `parse_target` skips `__pycache__/`. (Will exist organically after
   any test run; assert no `__pycache__` entries appear.)
5. `parse_target('totally/does/not/exist/')` raises
   `FileNotFoundError`.
6. Walking returns `[]` for a directory containing no `.py` files
   (use a `tempfile.TemporaryDirectory`).
7. `_dotted_name_for_path` for a file inside a package chain returns
   the proper dotted name.
8. `_dotted_name_for_path` for a loose file (parent has no
   `__init__.py`) returns `None` (signals fallback).
9. Walking deterministically sorts files alphabetically by full path.

### `tests/test_cli.py` (modify)

10. **Bare invocation** (`python -m assertions` with no args): use
    `cwd=` to point at a `tempfile.TemporaryDirectory` containing one
    test file with one passing `@test`. Exit 0; stdout has the test's
    `... ok` line.
11. **Directory target**: `python -m assertions
    tests/fixtures/runner/all_pass.py`'s parent (i.e.
    `tests/fixtures/runner/`) — currently the runner fixtures include
    files that intentionally raise (`class_enter_raises`, etc.). To
    avoid that complication, point at a controlled directory: build
    a `tempfile.TemporaryDirectory` with two passing test modules and
    walk it. Verify both run.
12. **Mixed targets**: `python -m assertions <tmpdir> tests.fixtures.runner.all_pass` — both targets contribute; output is in argv order.
13. **`sys.path` is restored**: spawn the CLI with a target that
    imports a package which would otherwise not be on path; verify
    that after the subprocess exits, the parent process's `sys.path`
    is unchanged. (Subprocess isolation makes this trivial — the
    parent doesn't share `sys.path` — so the test instead constructs
    a short-lived python invocation that imports `assertions.__main__`
    directly inside the same process and asserts `sys.path` is
    restored after `main(...)` returns.)
14. **Walked file with import error**: build a `tempfile.TemporaryDirectory`
    containing a `.py` file with `import this_does_not_exist` at
    module scope. The CLI should exit non-zero with `ModuleNotFoundError`
    in stderr. (Verifies "errors propagate".)

### Test fixtures

No new persistent fixtures under `tests/fixtures/`. The new tests use
`tempfile.TemporaryDirectory` to build controlled trees so that the
walker doesn't pick up the project's own intentionally-raising
fixtures.

## Acceptance

- `uv run python -m assertions tests/fixtures/runner/all_pass.py`
  still works (slice A behavior preserved).
- `python -m assertions` with no args, run inside a `tmpdir`
  containing one passing test, exits 0 and prints the test's
  `... ok` line.
- `python -m assertions <tmpdir>` with a controlled tree of two
  passing modules runs both, exit 0.
- After running the CLI in-process via `main(argv)`, `sys.path` is
  the same as before (asserted by tests).
- All previous tests still pass.
- `uv run mypy` reports no issues.
