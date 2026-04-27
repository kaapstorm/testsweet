# Split `_targets.py` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Run Python via uv:** All Python invocations use `uv run python ...` (or `uv run mypy`). Never call `python` or `mypy` directly.
>
> **Code style:** ruff-format runs as a pre-commit hook (`quote-style = 'single'`, `line-length = 79`). Use single quotes in new files. If a commit is rejected because the hook reformatted files, re-stage and commit again.

**Goal:** Split `src/assertions/_targets.py` into four files of ~25–80 lines each, named after their responsibility, leaving `parse_target` as a thin orchestrator.

**Architecture:** Three new modules — `_classify` (dotted-name resolution), `_walk` (directory walking + config-driven path expansion), `_loaders` (module loading from filesystem paths). `_targets.py` keeps `parse_target` and imports helpers from the three new modules. `__main__.py` reroutes its private-helper imports to the new modules. Tests follow: `tests/test_walk.py` and `tests/test_loaders.py` are new; `tests/test_targets.py` slims to `parse_target`-focused integration tests. No new tests; no behavior change.

**Tech Stack:** Python ≥3.11, `uv`, standard library only.

---

## File Structure

| Path | Action | Purpose |
|------|--------|---------|
| `src/assertions/_classify.py` | create | `_resolve_dotted` |
| `src/assertions/_walk.py` | create | `_walk_directory`, `_accepts_file`, `_is_excluded_dir`, `_resolve_include_paths`, `_build_exclude_set`, `_EXCLUDED_DIR_NAMES` |
| `src/assertions/_loaders.py` | create | `_exec_module_from_path`, `_load_path`, `_load_path_for_walk`, `_dotted_name_for_path` |
| `src/assertions/_targets.py` | rewrite | `parse_target` only; imports helpers from the three new modules |
| `src/assertions/__main__.py` | modify | Reroute private-helper imports to `_walk` and `_loaders` |
| `tests/test_loaders.py` | create | Holds `TestDottedNameForPath` and `TestExecModuleFromPath` |
| `tests/test_walk.py` | create | Holds `TestWalkDirectory` and `TestWalkDirectoryWithConfig` |
| `tests/test_targets.py` | modify | Keeps `TestParseTarget` and `TestParseTargetDirectory`; loses the moved classes |

No new tests in this slice — moves only.

---

## Task 1: Extract `_classify.py` with `_resolve_dotted`

**Files:**
- Create: `src/assertions/_classify.py`
- Modify: `src/assertions/_targets.py`

`_resolve_dotted` has no dependencies on other functions in `_targets.py`, so it moves cleanly.

- [ ] **Step 1: Create `src/assertions/_classify.py`**

```python
import importlib
from types import ModuleType


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
```

- [ ] **Step 2: Remove `_resolve_dotted` from `_targets.py` and import it instead**

In `src/assertions/_targets.py`:

- Delete the `_resolve_dotted` definition (currently lines 170–208).
- Delete the now-unused `import importlib` line at the top (if `importlib` is no longer referenced after this delete; it isn't — `_resolve_dotted` was the only caller). Verify with `grep -n importlib src/assertions/_targets.py`.
- Add `from assertions._classify import _resolve_dotted` to the imports.

- [ ] **Step 3: Run the full test suite**

Run:
```bash
uv run python -m unittest discover -s tests -v 2>&1 | tail -10
```

Expected: every test passes.

- [ ] **Step 4: Run mypy**

Run:
```bash
uv run mypy
```

Expected: `Success: no issues found`.

- [ ] **Step 5: Commit**

```bash
git add src/assertions/_classify.py src/assertions/_targets.py
git commit -m "Extract _resolve_dotted into _classify.py"
```

---

## Task 2: Extract `_loaders.py` with module-loading helpers

**Files:**
- Create: `src/assertions/_loaders.py`
- Modify: `src/assertions/_targets.py`
- Modify: `src/assertions/__main__.py`
- Modify: `tests/test_targets.py`

Move `_exec_module_from_path`, `_load_path`, `_load_path_for_walk`, `_dotted_name_for_path` together. `_load_path_for_walk` calls `_dotted_name_for_path` and `_exec_module_from_path` — they all live together in the new module.

- [ ] **Step 1: Create `src/assertions/_loaders.py`**

```python
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
    dotted, rootdir = _dotted_name_for_path(path)
    if dotted is not None and rootdir is not None:
        rootdir_str = str(rootdir)
        if rootdir_str not in sys.path:
            sys.path.insert(0, rootdir_str)
        return importlib.import_module(dotted)
    return _exec_module_from_path(path)


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
```

- [ ] **Step 2: Remove the four loader functions from `_targets.py` and import them**

In `src/assertions/_targets.py`:

- Delete the four functions (`_exec_module_from_path`, `_load_path`, `_load_path_for_walk`, `_dotted_name_for_path`).
- Add `from assertions._loaders import _load_path, _load_path_for_walk` (the two used by `parse_target`).
- Remove `import importlib`, `import importlib.util`, `import sys` if they are now unused. Use `grep -n "importlib\b\|importlib.util\|^import sys\b" src/assertions/_targets.py` to check; expected: no remaining hits except the new `from assertions._...` imports.

- [ ] **Step 3: Update `src/assertions/__main__.py` import**

Change:
```python
from assertions._targets import (
    _build_exclude_set,
    _load_path_for_walk,
    _resolve_include_paths,
    _walk_directory,
    parse_target,
)
```
to:
```python
from assertions._loaders import _load_path_for_walk
from assertions._targets import (
    _build_exclude_set,
    _resolve_include_paths,
    _walk_directory,
    parse_target,
)
```

(The remaining four imports still come from `_targets`; they get rerouted in Task 3.)

- [ ] **Step 4: Update `tests/test_targets.py` imports inside `TestExecModuleFromPath`**

The class has two methods that do `from assertions._targets import _exec_module_from_path`. Update both to:
```python
from assertions._loaders import _exec_module_from_path
```
Lines 267 and 277 in the current file.

- [ ] **Step 5: Run the full test suite**

Run:
```bash
uv run python -m unittest discover -s tests -v 2>&1 | tail -10
```

Expected: every test passes.

- [ ] **Step 6: Run mypy**

Run:
```bash
uv run mypy
```

Expected: `Success: no issues found`.

- [ ] **Step 7: Commit**

```bash
git add src/assertions/_loaders.py src/assertions/_targets.py src/assertions/__main__.py tests/test_targets.py
git commit -m "Extract module loaders into _loaders.py"
```

---

## Task 3: Extract `_walk.py` with walking + path expansion

**Files:**
- Create: `src/assertions/_walk.py`
- Modify: `src/assertions/_targets.py`
- Modify: `src/assertions/__main__.py`
- Modify: `tests/test_targets.py`

Move `_walk_directory`, `_accepts_file`, `_is_excluded_dir`, `_resolve_include_paths`, `_build_exclude_set`, plus the `_EXCLUDED_DIR_NAMES` constant.

- [ ] **Step 1: Create `src/assertions/_walk.py`**

```python
import fnmatch
import os
import pathlib

from assertions._config import DiscoveryConfig


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
```

- [ ] **Step 2: Remove the five functions and `_EXCLUDED_DIR_NAMES` from `_targets.py`; import what `parse_target` needs**

In `src/assertions/_targets.py`:

- Delete `_resolve_include_paths`, `_build_exclude_set`, `_walk_directory`, `_accepts_file`, `_is_excluded_dir`, `_EXCLUDED_DIR_NAMES`.
- Add `from assertions._walk import _walk_directory` (the only one `parse_target` calls).
- Remove `import fnmatch` and `import os` if unused. After this task `_targets.py` should import only what `parse_target` needs.

The full final `src/assertions/_targets.py` is:

```python
import pathlib
from types import ModuleType

from assertions._classify import _resolve_dotted
from assertions._config import DiscoveryConfig
from assertions._loaders import _load_path, _load_path_for_walk
from assertions._walk import _walk_directory


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
```

- [ ] **Step 3: Update `src/assertions/__main__.py` imports**

Change:
```python
from assertions._loaders import _load_path_for_walk
from assertions._targets import (
    _build_exclude_set,
    _resolve_include_paths,
    _walk_directory,
    parse_target,
)
```
to:
```python
from assertions._loaders import _load_path_for_walk
from assertions._targets import parse_target
from assertions._walk import (
    _build_exclude_set,
    _resolve_include_paths,
    _walk_directory,
)
```

- [ ] **Step 4: Update `tests/test_targets.py` imports inside `TestWalkDirectoryWithConfig`**

The class's three methods do `from assertions._targets import _walk_directory`. Update each:
```python
from assertions._walk import _walk_directory
```
There are three occurrences inside the class body (one per test method that imports it).

- [ ] **Step 5: Update the top-of-file import in `tests/test_targets.py`**

The current top-of-file import is:
```python
from assertions._targets import (
    _dotted_name_for_path,
    _walk_directory,
    parse_target,
)
```

Update to:
```python
from assertions._loaders import _dotted_name_for_path
from assertions._targets import parse_target
from assertions._walk import _walk_directory
```

- [ ] **Step 6: Run the full test suite**

Run:
```bash
uv run python -m unittest discover -s tests -v 2>&1 | tail -10
```

Expected: every test passes.

- [ ] **Step 7: Run mypy**

Run:
```bash
uv run mypy
```

Expected: `Success: no issues found`.

- [ ] **Step 8: Commit**

```bash
git add src/assertions/_walk.py src/assertions/_targets.py src/assertions/__main__.py tests/test_targets.py
git commit -m "Extract directory walker into _walk.py"
```

---

## Task 4: Move `TestDottedNameForPath` and `TestExecModuleFromPath` to `tests/test_loaders.py`

**Files:**
- Create: `tests/test_loaders.py`
- Modify: `tests/test_targets.py`

- [ ] **Step 1: Create `tests/test_loaders.py`**

```python
import pathlib
import tempfile
import unittest

from assertions._loaders import _dotted_name_for_path


class TestDottedNameForPath(unittest.TestCase):
    def test_returns_dotted_name_for_packaged_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            pkg = root / 'pkg'
            pkg.mkdir()
            (pkg / '__init__.py').write_text('')
            sub = pkg / 'sub'
            sub.mkdir()
            (sub / '__init__.py').write_text('')
            target = sub / 'mod.py'
            target.write_text('')
            dotted, rootdir = _dotted_name_for_path(target)
            self.assertEqual(dotted, 'pkg.sub.mod')
            self.assertEqual(rootdir, root)

    def test_returns_none_for_loose_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            target = root / 'loose.py'
            target.write_text('')
            dotted, rootdir = _dotted_name_for_path(target)
            self.assertIsNone(dotted)
            self.assertIsNone(rootdir)

    def test_top_level_package_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            pkg = root / 'pkg'
            pkg.mkdir()
            (pkg / '__init__.py').write_text('')
            target = pkg / 'mod.py'
            target.write_text('')
            dotted, rootdir = _dotted_name_for_path(target)
            self.assertEqual(dotted, 'pkg.mod')
            self.assertEqual(rootdir, root)


class TestExecModuleFromPath(unittest.TestCase):
    def test_loads_a_simple_module(self):
        from assertions._loaders import _exec_module_from_path

        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / 'demo.py'
            path.write_text('value = 42\n')
            module = _exec_module_from_path(path)
        self.assertEqual(getattr(module, 'value'), 42)
        self.assertEqual(module.__name__, 'demo')

    def test_unloadable_path_raises_import_error(self):
        from assertions._loaders import _exec_module_from_path

        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / 'missing.py'
            with self.assertRaises((ImportError, FileNotFoundError)):
                _exec_module_from_path(path)


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Remove `TestDottedNameForPath` and `TestExecModuleFromPath` from `tests/test_targets.py`**

Delete the two class definitions (currently `TestDottedNameForPath` at line 179 and `TestExecModuleFromPath` at line 265). Also delete the top-of-file import of `_dotted_name_for_path` (already updated in Task 3) — `tests/test_targets.py` no longer needs it. The remaining top-of-file imports from the previous tasks should be:

```python
from assertions._targets import parse_target
from assertions._walk import _walk_directory
```

(Plus the `import importlib`, `import os`, `import pathlib`, `import tempfile`, `import unittest` already present.)

- [ ] **Step 3: Run the full test suite**

Run:
```bash
uv run python -m unittest discover -s tests -v 2>&1 | tail -10
```

Expected: every test passes; total count unchanged.

- [ ] **Step 4: Run mypy**

Run:
```bash
uv run mypy
```

Expected: `Success: no issues found`.

- [ ] **Step 5: Commit**

```bash
git add tests/test_loaders.py tests/test_targets.py
git commit -m "Move dotted-name and exec-module tests to test_loaders.py"
```

---

## Task 5: Move `TestWalkDirectory` and `TestWalkDirectoryWithConfig` to `tests/test_walk.py`

**Files:**
- Create: `tests/test_walk.py`
- Modify: `tests/test_targets.py`

- [ ] **Step 1: Create `tests/test_walk.py` by moving the two classes**

The new file holds both classes plus the imports they need.

```python
import pathlib
import tempfile
import unittest
import unittest.mock

from assertions._walk import _walk_directory


class TestWalkDirectory(unittest.TestCase):
    def test_returns_py_files_alphabetical(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / 'b.py').write_text('')
            (root / 'a.py').write_text('')
            (root / 'c.py').write_text('')
            paths = _walk_directory(root)
            self.assertEqual(
                [p.name for p in paths],
                ['a.py', 'b.py', 'c.py'],
            )

    def test_recurses_subdirectories(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / 'top.py').write_text('')
            sub = root / 'sub'
            sub.mkdir()
            (sub / 'inner.py').write_text('')
            paths = _walk_directory(root)
            names = [p.relative_to(root).as_posix() for p in paths]
            self.assertEqual(names, ['sub/inner.py', 'top.py'])

    def test_excludes_hidden_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / 'visible.py').write_text('')
            hidden = root / '.hidden'
            hidden.mkdir()
            (hidden / 'inside.py').write_text('')
            paths = _walk_directory(root)
            self.assertEqual(
                [p.name for p in paths],
                ['visible.py'],
            )

    def test_excludes_pycache(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / 'visible.py').write_text('')
            cache = root / '__pycache__'
            cache.mkdir()
            (cache / 'inside.py').write_text('')
            paths = _walk_directory(root)
            self.assertEqual(
                [p.name for p in paths],
                ['visible.py'],
            )

    def test_excludes_node_modules(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / 'visible.py').write_text('')
            nm = root / 'node_modules'
            nm.mkdir()
            (nm / 'inside.py').write_text('')
            paths = _walk_directory(root)
            self.assertEqual(
                [p.name for p in paths],
                ['visible.py'],
            )

    def test_empty_when_no_py_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = _walk_directory(pathlib.Path(tmp))
            self.assertEqual(paths, [])


class TestWalkDirectoryWithConfig(unittest.TestCase):
    def test_test_files_filter_keeps_matching_names(self):
        from assertions._config import DiscoveryConfig
        from assertions._walk import _walk_directory

        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / 'test_a.py').write_text('')
            (root / 'b_tests.py').write_text('')
            (root / 'helper.py').write_text('')
            config = DiscoveryConfig(
                test_files=('test_*.py', '*_tests.py'),
            )
            paths = _walk_directory(root, config=config, excluded=set())
        self.assertEqual(
            sorted(p.name for p in paths),
            ['b_tests.py', 'test_a.py'],
        )

    def test_test_files_filter_with_no_match(self):
        from assertions._config import DiscoveryConfig
        from assertions._walk import _walk_directory

        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / 'helper.py').write_text('')
            config = DiscoveryConfig(test_files=('test_*.py',))
            paths = _walk_directory(root, config=config, excluded=set())
        self.assertEqual(paths, [])

    def test_excluded_set_drops_files(self):
        from assertions._config import DiscoveryConfig
        from assertions._walk import _walk_directory

        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            keep = root / 'keep.py'
            drop = root / 'drop.py'
            keep.write_text('')
            drop.write_text('')
            paths = _walk_directory(
                root,
                config=DiscoveryConfig(),
                excluded={drop.resolve()},
            )
        self.assertEqual(
            [p.name for p in paths],
            ['keep.py'],
        )

    def test_default_args_preserve_old_behavior(self):
        from assertions._walk import _walk_directory

        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / 'a.py').write_text('')
            (root / 'b.py').write_text('')
            paths_no_args = _walk_directory(root)
        self.assertEqual(
            sorted(p.name for p in paths_no_args),
            ['a.py', 'b.py'],
        )

    def test_filters_apply_with_excluded(self):
        from assertions._config import DiscoveryConfig
        from assertions._walk import _walk_directory

        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / 'test_a.py').write_text('')
            test_b = root / 'test_b.py'
            test_b.write_text('')
            config = DiscoveryConfig(test_files=('test_*.py',))
            paths = _walk_directory(
                root,
                config=config,
                excluded={test_b.resolve()},
            )
        self.assertEqual(
            [p.name for p in paths],
            ['test_a.py'],
        )


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Remove `TestWalkDirectory` and `TestWalkDirectoryWithConfig` from `tests/test_targets.py`**

Delete both class definitions. After this delete, `tests/test_targets.py` should contain only:
- The module-level imports.
- `_FIXTURES` constant.
- `TestParseTarget` class.
- `TestParseTargetDirectory` class.
- The trailing `if __name__ == '__main__':` block.

The top-of-file imports should be:

```python
import importlib
import pathlib
import tempfile
import unittest

from assertions._targets import parse_target
```

(`_walk_directory` is no longer imported in this file. `os` was only used by the moved walker tests; remove if present.)

- [ ] **Step 3: Run the full test suite**

Run:
```bash
uv run python -m unittest discover -s tests -v 2>&1 | tail -10
```

Expected: every test passes; total count unchanged.

- [ ] **Step 4: Run mypy**

Run:
```bash
uv run mypy
```

Expected: `Success: no issues found`.

- [ ] **Step 5: Commit**

```bash
git add tests/test_walk.py tests/test_targets.py
git commit -m "Move walker tests to test_walk.py"
```

---

## Task 6: Smoke-test the refactor

**Files:** none — verification only.

- [ ] **Step 1: examples still pass via the CLI**

Run:
```bash
uv run python -m assertions examples.functions; echo "exit=$?"
uv run python -m assertions examples.classes; echo "exit=$?"
uv run python -m assertions examples.catches; echo "exit=$?"
```

Expected: all three exit 0 with their previously-expected output.

- [ ] **Step 2: existing CLI surface still works**

Run:
```bash
uv run python -m assertions tests/fixtures/runner/all_pass.py; echo "exit=$?"
uv run python -m assertions tests.fixtures.runner.class_simple.Simple.first; echo "exit=$?"
```

Expected: both exit 0.

- [ ] **Step 3: line counts and module shape**

Run:
```bash
wc -l src/assertions/*.py
```

Expected: `_targets.py` is now ~25 lines; `_classify.py` ~40 lines; `_walk.py` ~80 lines; `_loaders.py` ~50 lines. Total approximately the same as before.

- [ ] **Step 4: confirm symbol locations**

Run:
```bash
git grep -n "^def _resolve_dotted\b" src/
git grep -n "^def _walk_directory\b" src/
git grep -n "^def _exec_module_from_path\b" src/
git grep -n "^def parse_target\b" src/
```

Expected:
- `_resolve_dotted` in `src/assertions/_classify.py`.
- `_walk_directory` in `src/assertions/_walk.py`.
- `_exec_module_from_path` in `src/assertions/_loaders.py`.
- `parse_target` in `src/assertions/_targets.py`.

Each defined exactly once.

- [ ] **Step 5: No commit**

If any smoke step fails, return to the relevant earlier task and diagnose.

---

## Self-Review

- **Spec coverage:**
  - `_classify.py` created with `_resolve_dotted` — Task 1 ✓
  - `_walk.py` created with walker + path-expansion functions — Task 3 ✓
  - `_loaders.py` created with module-loading functions — Task 2 ✓
  - `_targets.py` shrunk to thin orchestrator — Task 3 step 2 ✓
  - `__main__.py` reroutes private imports to new modules — Tasks 2 step 3 + 3 step 3 ✓
  - `tests/test_loaders.py` holds `TestDottedNameForPath` + `TestExecModuleFromPath` — Task 4 ✓
  - `tests/test_walk.py` holds `TestWalkDirectory` + `TestWalkDirectoryWithConfig` — Task 5 ✓
  - `tests/test_targets.py` slimmed to `TestParseTarget` + `TestParseTargetDirectory` — Task 4 step 2 + Task 5 step 2 ✓
  - No new tests, no behavior change — every task verifies via the existing suite ✓
  - `tests/test_config.py` unchanged — confirmed by absence in any task ✓
  - mypy clean — Tasks 1-5 ✓
  - examples still pass — Task 6 step 1 ✓
- **Placeholder scan:** none.
- **Type consistency:**
  - `_resolve_dotted` signature `(target: str) -> tuple[ModuleType, list[str] | None]` consistent across `_classify.py` definition and `_targets.py` import.
  - `_walk_directory(root, config=None, excluded=None)` consistent across `_walk.py` definition and consumers (`_targets.py`, `__main__.py`, tests).
  - `_load_path(target: str) -> ModuleType` and `_load_path_for_walk(path: pathlib.Path) -> ModuleType` consistent.
  - `_dotted_name_for_path(path) -> tuple[str | None, pathlib.Path | None]` consistent.
  - `_exec_module_from_path(path) -> ModuleType` consistent.
  - `_EXCLUDED_DIR_NAMES` is the only constant moved; lives only in `_walk.py` after Task 3.
