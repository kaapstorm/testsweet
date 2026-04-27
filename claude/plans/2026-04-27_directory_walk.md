# Bare Auto-Discovery + Directory Args Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Run Python via uv:** All Python invocations use `uv run python ...` (or `uv run mypy`). Never call `python` or `mypy` directly.
>
> **Code style:** ruff-format runs as a pre-commit hook (`quote-style = 'single'`, `line-length = 79`). Use single quotes in new files. If a commit is rejected because the hook reformatted files, re-stage and commit again.

**Goal:** Allow `python -m assertions` to walk the current working directory when invoked with no arguments, and to walk any directory passed as a target. Reuse the existing `run(module)` machinery for each discovered module.

**Architecture:** Add a directory branch to `parse_target` and widen its return type to a list. The directory branch walks `os.walk` with built-in exclusions (hidden dirs, `__pycache__`, `node_modules`), computes a package-aware dotted name for each `.py` file (walking up `__init__.py` chains), adds the rootdir to `sys.path` if needed, and uses `importlib.import_module` — falling back to `spec_from_file_location` for loose files. The CLI defaults to `argv = ['.']` when called with no args, snapshots `sys.path` around the run, and restores it in a `finally`.

**Tech Stack:** Python ≥3.11, `uv`, standard library only (`os`, `pathlib`, `importlib`).

---

## File Structure

| Path | Action | Purpose |
|------|--------|---------|
| `src/assertions/_targets.py` | modify | Widen `parse_target` to `list[...]`; add `_walk_directory`, `_dotted_name_for_path`, `_load_path_or_walk` |
| `src/assertions/__main__.py` | modify | Default `argv` to `['.']`; iterate list-shaped `parse_target` result; snapshot+restore `sys.path` |
| `tests/test_targets.py` | modify | Update existing tests for list-shape; add directory-walk tests |
| `tests/test_cli.py` | modify | Add CLI tests for bare invocation, directory args, sys.path restore, walk-with-import-error |

---

## Task 1: Widen `parse_target` return type to `list[...]`

**Files:**
- Modify: `src/assertions/_targets.py`
- Modify: `tests/test_targets.py`
- Modify: `src/assertions/__main__.py`

This is a pure refactor — no behavior change. `parse_target` returns a list with a single element for every existing case. Existing tests are updated.

- [ ] **Step 1: Update `tests/test_targets.py` to expect lists**

Replace each existing assertion that reads `parse_target(...)` as a tuple with one that reads `parse_target(...)[0]`. The full updated file body (everything between imports and `if __name__ == '__main__':`) becomes:

```python
class TestParseTarget(unittest.TestCase):
    def test_dotted_module_no_selector(self):
        result = parse_target('tests.fixtures.runner.all_pass')
        self.assertEqual(len(result), 1)
        module, names = result[0]
        expected = importlib.import_module(
            'tests.fixtures.runner.all_pass',
        )
        self.assertIs(module, expected)
        self.assertIsNone(names)

    def test_relative_file_path(self):
        result = parse_target(
            'tests/fixtures/runner/all_pass.py',
        )
        self.assertEqual(len(result), 1)
        module, names = result[0]
        self.assertIsNone(names)
        self.assertTrue(hasattr(module, 'passes_one'))
        self.assertTrue(hasattr(module, 'passes_two'))

    def test_relative_file_path_with_dot(self):
        result = parse_target(
            './tests/fixtures/runner/all_pass.py',
        )
        self.assertEqual(len(result), 1)
        module, names = result[0]
        self.assertIsNone(names)
        self.assertTrue(hasattr(module, 'passes_one'))

    def test_absolute_file_path(self):
        path = (_FIXTURES / 'all_pass.py').resolve()
        result = parse_target(str(path))
        self.assertEqual(len(result), 1)
        module, names = result[0]
        self.assertIsNone(names)
        self.assertTrue(hasattr(module, 'passes_one'))

    def test_dotted_selector_one_segment(self):
        result = parse_target(
            'tests.fixtures.runner.all_pass.passes_one',
        )
        self.assertEqual(len(result), 1)
        module, names = result[0]
        expected = importlib.import_module(
            'tests.fixtures.runner.all_pass',
        )
        self.assertIs(module, expected)
        self.assertEqual(names, ['passes_one'])

    def test_dotted_selector_class_only(self):
        result = parse_target(
            'tests.fixtures.runner.class_simple.Simple',
        )
        self.assertEqual(len(result), 1)
        module, names = result[0]
        expected = importlib.import_module(
            'tests.fixtures.runner.class_simple',
        )
        self.assertIs(module, expected)
        self.assertEqual(names, ['Simple'])

    def test_dotted_selector_class_method(self):
        result = parse_target(
            'tests.fixtures.runner.class_simple.Simple.first',
        )
        self.assertEqual(len(result), 1)
        module, names = result[0]
        expected = importlib.import_module(
            'tests.fixtures.runner.class_simple',
        )
        self.assertIs(module, expected)
        self.assertEqual(names, ['Simple.first'])

    def test_dotted_too_many_segments(self):
        with self.assertRaises(LookupError):
            parse_target(
                'tests.fixtures.runner.class_simple.'
                'Simple.first.extra',
            )

    def test_dotted_no_importable_prefix(self):
        with self.assertRaises(ModuleNotFoundError):
            parse_target('totally.not.a.module')

    def test_internal_import_error_propagates(self):
        with self.assertRaises(ModuleNotFoundError) as ctx:
            parse_target('tests.fixtures.runner.has_broken_import')
        self.assertEqual(
            ctx.exception.name,
            'this_dependency_does_not_exist',
        )
```

- [ ] **Step 2: Run the tests; they must fail**

Run:
```bash
uv run python -m unittest tests.test_targets -v
```

Expected: every test fails because the existing `parse_target` returns a 2-tuple, so `len(result)` and `result[0]` raise `TypeError: object of type ... has no len()` (since you can't `len()` a tuple of two heterogeneous things — actually `len(tuple) == 2`, so the assertion `self.assertEqual(len(result), 1)` fails with `2 != 1`). Either way the tests don't pass.

- [ ] **Step 3: Update `src/assertions/_targets.py` to return a list**

Replace the file contents with:

```python
import importlib
import importlib.util
import pathlib
from types import ModuleType


def parse_target(
    target: str,
) -> list[tuple[ModuleType, list[str] | None]]:
    if '/' in target or target.endswith('.py'):
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
                exc.name == head
                or head.startswith(exc.name + '.')
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

- [ ] **Step 4: Update `__main__.py` to iterate the list**

The current `for arg in argv: module, names = parse_target(arg); _add_to_groups(...)` becomes:

```python
for arg in argv:
    for module, names in parse_target(arg):
        _add_to_groups(groups, module, names)
```

The full file should now read:

```python
import sys
from types import ModuleType

from assertions._runner import run
from assertions._targets import parse_target


USAGE = 'usage: python -m assertions <target> [<target>...]'


def main(argv: list[str]) -> int:
    if len(argv) < 1:
        print(USAGE, file=sys.stderr)
        return 2
    groups: list[tuple[ModuleType, list[str] | None]] = []
    for arg in argv:
        for module, names in parse_target(arg):
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
```

- [ ] **Step 5: Run the full suite to confirm no regressions**

Run:
```bash
uv run python -m unittest discover -s tests -v 2>&1 | tail -10
```

Expected: every test passes, including the existing CLI tests (file paths, selectors, multi-target). No new behavior has been added yet — purely a shape change.

- [ ] **Step 6: Run mypy**

Run:
```bash
uv run mypy
```

Expected: `Success: no issues found`.

- [ ] **Step 7: Commit**

```bash
git add src/assertions/_targets.py src/assertions/__main__.py tests/test_targets.py
git commit -m "Widen parse_target to return list of (module, names) entries"
```

---

## Task 2: Write failing tests for `_walk_directory` and `_dotted_name_for_path`

**Files:**
- Modify: `tests/test_targets.py`

- [ ] **Step 1: Append a new test class to `tests/test_targets.py`**

Add (before `if __name__ == '__main__':`):

```python
import os
import tempfile

from assertions._targets import (
    _dotted_name_for_path,
    _walk_directory,
)


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


class TestParseTargetDirectory(unittest.TestCase):
    def test_directory_yields_one_entry_per_py_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / 'a.py').write_text(
                'from assertions import test\n'
                '@test\n'
                'def t():\n'
                '    pass\n'
            )
            (root / 'b.py').write_text(
                'from assertions import test\n'
                '@test\n'
                'def t():\n'
                '    pass\n'
            )
            result = parse_target(str(root))
            self.assertEqual(len(result), 2)
            for module, names in result:
                self.assertIsNone(names)

    def test_nonexistent_directory_raises(self):
        with self.assertRaises((FileNotFoundError, ImportError)):
            parse_target('/this/path/really/should/not/exist/abc/')

    def test_empty_directory_returns_empty_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = parse_target(str(pathlib.Path(tmp)))
            self.assertEqual(result, [])
```

(Note: the `import os` and `import tempfile` need to land at the top of the file with the other imports. Add them with the existing import block; `pathlib` is already imported from earlier additions.)

- [ ] **Step 2: Run the tests; they must fail on import**

Run:
```bash
uv run python -m unittest tests.test_targets -v
```

Expected: `ImportError: cannot import name '_walk_directory' from 'assertions._targets'`.

- [ ] **Step 3: Commit**

```bash
git add tests/test_targets.py
git commit -m "Add failing tests for directory walk and package-aware import"
```

---

## Task 3: Implement `_walk_directory`, `_dotted_name_for_path`, and the directory branch of `parse_target`

**Files:**
- Modify: `src/assertions/_targets.py`

- [ ] **Step 1: Replace the file contents**

```python
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
    if '/' in target or target.endswith('.py'):
        path = pathlib.Path(target).resolve()
        if path.is_dir():
            return [
                (_load_path_for_walk(p), None)
                for p in _walk_directory(path)
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
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(
            d for d in dirnames if not _is_excluded_dir(d)
        )
        for name in sorted(filenames):
            if name.endswith('.py'):
                out.append(pathlib.Path(dirpath) / name)
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
                exc.name == head
                or head.startswith(exc.name + '.')
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

- [ ] **Step 2: Run the tests; they must pass**

Run:
```bash
uv run python -m unittest tests.test_targets -v
```

Expected: all `tests.test_targets` tests pass (the existing ones and the new ones from Task 2 — about 19 in total).

- [ ] **Step 3: Run the full suite**

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
git add src/assertions/_targets.py
git commit -m "Add directory walk and package-aware import to parse_target"
```

---

## Task 4: Write failing CLI tests for bare invocation and directory args

**Files:**
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Append test methods to the existing `class TestCli(unittest.TestCase):` body**

Add inside the class (before `if __name__ == '__main__':`):

```python
    def test_bare_invocation_walks_cwd(self):
        import tempfile
        import textwrap

        with tempfile.TemporaryDirectory() as tmp:
            (pathlib.Path(tmp) / 'test_simple.py').write_text(
                textwrap.dedent("""
                    from assertions import test

                    @test
                    def passes():
                        assert True
                """).lstrip()
            )
            result = subprocess.run(
                [sys.executable, '-m', 'assertions'],
                capture_output=True,
                text=True,
                cwd=tmp,
            )
        self.assertEqual(result.returncode, 0)
        self.assertIn('passes ... ok', result.stdout)

    def test_directory_argument_walks_recursively(self):
        import tempfile
        import textwrap

        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / 'test_a.py').write_text(
                textwrap.dedent("""
                    from assertions import test

                    @test
                    def passes_a():
                        assert True
                """).lstrip()
            )
            sub = root / 'sub'
            sub.mkdir()
            (sub / 'test_b.py').write_text(
                textwrap.dedent("""
                    from assertions import test

                    @test
                    def passes_b():
                        assert True
                """).lstrip()
            )
            result = subprocess.run(
                [sys.executable, '-m', 'assertions', tmp],
                capture_output=True,
                text=True,
                cwd=_REPO_ROOT,
            )
        self.assertEqual(result.returncode, 0)
        self.assertIn('passes_a ... ok', result.stdout)
        self.assertIn('passes_b ... ok', result.stdout)

    def test_walked_file_with_import_error_propagates(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            (pathlib.Path(tmp) / 'broken.py').write_text(
                'import this_does_not_exist_assertions_test\n'
            )
            result = subprocess.run(
                [sys.executable, '-m', 'assertions', tmp],
                capture_output=True,
                text=True,
                cwd=_REPO_ROOT,
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('ModuleNotFoundError', result.stderr)

    def test_sys_path_is_restored_after_main(self):
        import importlib
        import tempfile
        import textwrap

        from assertions import __main__ as cli_main

        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            pkg = root / 'walkpkg'
            pkg.mkdir()
            (pkg / '__init__.py').write_text('')
            (pkg / 'test_inside.py').write_text(
                textwrap.dedent("""
                    from assertions import test

                    @test
                    def passes():
                        assert True
                """).lstrip()
            )
            saved = list(sys.path)
            try:
                cli_main.main([str(root)])
            finally:
                # main should restore sys.path even if it raises.
                pass
            self.assertEqual(sys.path, saved)
            # Reload to clean up sys.modules pollution from the test.
            for name in list(sys.modules):
                if name == 'walkpkg' or name.startswith('walkpkg.'):
                    del sys.modules[name]
```

`pathlib` and `subprocess` are already imported at the module top; `_REPO_ROOT` is already defined for the existing CLI tests.

- [ ] **Step 2: Run the tests; they must fail**

Run:
```bash
uv run python -m unittest tests.test_cli -v
```

Expected: each new test fails. The `bare_invocation` test fails because the CLI currently exits 2 on no args. The `directory_argument` test fails because `parse_target` raises `ImportError` (it tries to load a directory as a `.py` file). The `walked_file_with_import_error` test fails for the same reason. The `sys_path_is_restored` test fails because `main` doesn't snapshot/restore `sys.path`.

- [ ] **Step 3: Commit**

```bash
git add tests/test_cli.py
git commit -m "Add failing CLI tests for bare invocation and directory walk"
```

---

## Task 5: Update `__main__.py` to default to cwd and snapshot/restore `sys.path`

**Files:**
- Modify: `src/assertions/__main__.py`

- [ ] **Step 1: Replace the file contents**

```python
import sys
from types import ModuleType

from assertions._runner import run
from assertions._targets import parse_target


USAGE = 'usage: python -m assertions [<target>...]'


def main(argv: list[str]) -> int:
    if not argv:
        argv = ['.']
    saved_sys_path = list(sys.path)
    try:
        groups: list[tuple[ModuleType, list[str] | None]] = []
        for arg in argv:
            for module, names in parse_target(arg):
                _add_to_groups(groups, module, names)
        failed = False
        for module, merged_names in groups:
            results = run(module, names=merged_names)
            for name, exc in results:
                if exc is None:
                    print(f'{name} ... ok')
                else:
                    print(
                        f'{name} ... FAIL: '
                        f'{type(exc).__name__}: {exc}'
                    )
                    failed = True
        return 1 if failed else 0
    finally:
        sys.path[:] = saved_sys_path


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
```

- [ ] **Step 2: Run the new CLI tests; they must pass**

Run:
```bash
uv run python -m unittest tests.test_cli -v
```

Expected: every test passes (the existing ones and the four new ones from Task 4).

- [ ] **Step 3: Run the full suite**

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
git add src/assertions/__main__.py
git commit -m "Default to cwd; snapshot and restore sys.path around the run"
```

---

## Task 6: Smoke-test bare invocation and directory args

**Files:** none — verification only.

- [ ] **Step 1: Build a controlled tmp tree and run bare invocation**

Run:
```bash
uv run python -c "
import pathlib, subprocess, sys, tempfile, textwrap
with tempfile.TemporaryDirectory() as tmp:
    (pathlib.Path(tmp) / 'test_a.py').write_text(textwrap.dedent('''
        from assertions import test
        @test
        def passes():
            assert True
    ''').lstrip())
    r = subprocess.run([sys.executable, '-m', 'assertions'], cwd=tmp, capture_output=True, text=True)
    print('exit:', r.returncode)
    print('stdout:', r.stdout)
    print('stderr:', r.stderr)
"
```

Expected: `exit: 0`, stdout contains `passes ... ok`, no stderr noise.

- [ ] **Step 2: Run with a directory argument**

Run:
```bash
uv run python -c "
import pathlib, subprocess, sys, tempfile, textwrap
with tempfile.TemporaryDirectory() as tmp:
    root = pathlib.Path(tmp)
    (root / 'test_a.py').write_text(textwrap.dedent('''
        from assertions import test
        @test
        def passes_a():
            assert True
    ''').lstrip())
    sub = root / 'sub'
    sub.mkdir()
    (sub / 'test_b.py').write_text(textwrap.dedent('''
        from assertions import test
        @test
        def passes_b():
            assert True
    ''').lstrip())
    r = subprocess.run([sys.executable, '-m', 'assertions', tmp], capture_output=True, text=True)
    print('exit:', r.returncode)
    print('stdout:', r.stdout)
"
```

Expected: `exit: 0`, stdout contains both `passes_a ... ok` and `passes_b ... ok`.

- [ ] **Step 3: Existing examples still pass**

Run:
```bash
uv run python -m assertions examples.functions; echo "exit=$?"
uv run python -m assertions examples.classes; echo "exit=$?"
uv run python -m assertions examples.catches; echo "exit=$?"
```

Expected: all three exit 0 with their previously-expected output.

- [ ] **Step 4: Existing CLI surface still works**

Run:
```bash
uv run python -m assertions tests/fixtures/runner/all_pass.py; echo "exit=$?"
uv run python -m assertions tests.fixtures.runner.class_simple.Simple.first; echo "exit=$?"
```

Expected: both exit 0 with appropriate output (file-path target works; selector still narrows).

- [ ] **Step 5: No commit**

If any smoke step fails, return to the relevant earlier task and diagnose.

---

## Self-Review

- **Spec coverage:**
  - Bare `python -m assertions` walks cwd — Task 5 (`if not argv: argv = ['.']`); Task 4 test 1 ✓
  - Directory target walks tree — Task 3 (`parse_target` directory branch); Task 4 test 2 ✓
  - File pattern: every `*.py` — Task 3 `_walk_directory` ✓
  - Built-in exclusions (hidden dirs, `__pycache__`, `node_modules`) — Task 3 `_is_excluded_dir`; Task 2 tests 3-5 ✓
  - Package-aware import via `__init__.py` chain walk — Task 3 `_dotted_name_for_path`; Task 2 tests 7-9 ✓
  - Loose-file fallback to `spec_from_file_location` — Task 3 `_load_path_for_walk` else-branch; Task 2 test 8 (returns None signaling fallback) ✓
  - `sys.path` snapshot + restore — Task 5; Task 4 test 4 ✓
  - Import errors propagate — Task 3 (no try/except in walk path); Task 4 test 3 ✓
  - `parse_target` returns `list[...]` — Task 1 ✓
  - Directory argument with no `.py` files returns `[]` — Task 2 `test_empty_directory_returns_empty_list` ✓
  - Nonexistent directory raises — Task 2 `test_nonexistent_directory_raises` ✓
  - Walking is alphabetical and deterministic — Task 2 `test_returns_py_files_alphabetical`, `test_recurses_subdirectories` ✓
  - mypy clean — Tasks 1, 3, 5 ✓
  - Examples still pass — Task 6 step 3 ✓
- **Placeholder scan:** none.
- **Type consistency:**
  - `parse_target` return type `list[tuple[ModuleType, list[str] | None]]` is consistent across `_targets.py`, `__main__.py`, and tests.
  - `_walk_directory` returns `list[pathlib.Path]` consistently in implementation and tests.
  - `_dotted_name_for_path` returns `tuple[str | None, pathlib.Path | None]` consistently.
  - `_EXCLUDED_DIR_NAMES` is a `frozenset[str]`; `_is_excluded_dir` accepts `str` returns `bool`.
