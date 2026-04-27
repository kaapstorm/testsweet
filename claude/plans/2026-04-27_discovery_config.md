# pyproject.toml Discovery Config Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Run Python via uv:** All Python invocations use `uv run python ...` (or `uv run mypy`). Never call `python` or `mypy` directly.
>
> **Code style:** ruff-format runs as a pre-commit hook (`quote-style = 'single'`, `line-length = 79`). Use single quotes in new files. If a commit is rejected because the hook reformatted files, re-stage and commit again.

**Goal:** Add `[tool.assertions.discovery]` configuration in `pyproject.toml` that narrows the default match-all-`*.py` walk via three glob-pattern lists: `include_paths`, `exclude_paths`, `test_files`. Apply config during directory walks. Refactor `_walk_directory` to use `os.scandir`. Extract a shared `_exec_module_from_path` helper.

**Architecture:** A new `_config.py` walks up from cwd to find `pyproject.toml`, parses `[tool.assertions.discovery]` strictly (raises `ConfigurationError` on unknown keys or wrong types), and returns a frozen `DiscoveryConfig` dataclass. The CLI loads config once at the start of `main`, pre-computes the exclude set via `Path.glob`, and passes both into the walker. `_walk_directory` is refactored to take a `config` parameter and an `excluded` set, applying `test_files` filtering via `fnmatch.fnmatch` and `exclude_paths` via set membership. The walker also moves to `os.scandir`. `_load_path` and `_load_path_for_walk` share a new `_exec_module_from_path` helper.

**Tech Stack:** Python ≥3.11 (`tomllib` is stdlib), `uv`, standard library only.

---

## File Structure

| Path | Action | Purpose |
|------|--------|---------|
| `src/assertions/_config.py` | create | `DiscoveryConfig`, `ConfigurationError`, `load_config` |
| `src/assertions/_targets.py` | modify | `os.scandir`-based `_walk_directory`; `_exec_module_from_path`; config-aware walker; include-path resolution |
| `src/assertions/__main__.py` | modify | Load config at start of `main`; build exclude set; thread config through |
| `src/assertions/__init__.py` | modify | Re-export `ConfigurationError` |
| `tests/test_config.py` | create | Schema parsing, walk-up, validation errors |
| `tests/test_targets.py` | modify | Add config-aware walker tests; `_exec_module_from_path` test |
| `tests/test_cli.py` | modify | Add CLI tests with `pyproject.toml` configs |

---

## Task 1: Add `_config.py` with `DiscoveryConfig`, `ConfigurationError`, `load_config`

**Files:**
- Create: `src/assertions/_config.py`
- Create: `tests/test_config.py`
- Modify: `src/assertions/__init__.py`

- [ ] **Step 1: Write failing tests in `tests/test_config.py`**

```python
import pathlib
import tempfile
import textwrap
import unittest

from assertions import ConfigurationError
from assertions._config import DiscoveryConfig, load_config


class TestLoadConfig(unittest.TestCase):
    def test_no_pyproject_returns_empty_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = load_config(pathlib.Path(tmp))
        self.assertEqual(config, DiscoveryConfig())
        self.assertIsNone(config.project_root)

    def test_pyproject_without_discovery_section(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / 'pyproject.toml').write_text(
                textwrap.dedent("""
                    [project]
                    name = "demo"
                """).lstrip()
            )
            config = load_config(root)
        self.assertEqual(config.include_paths, ())
        self.assertEqual(config.exclude_paths, ())
        self.assertEqual(config.test_files, ())
        self.assertEqual(config.project_root, root.resolve())

    def test_full_discovery_section(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / 'pyproject.toml').write_text(
                textwrap.dedent("""
                    [tool.assertions.discovery]
                    include_paths = ["tests/**"]
                    exclude_paths = ["src/vendored/**"]
                    test_files = ["test_*.py", "*_tests.py"]
                """).lstrip()
            )
            config = load_config(root)
        self.assertEqual(config.include_paths, ('tests/**',))
        self.assertEqual(
            config.exclude_paths, ('src/vendored/**',),
        )
        self.assertEqual(
            config.test_files, ('test_*.py', '*_tests.py'),
        )
        self.assertEqual(config.project_root, root.resolve())

    def test_walks_up_from_subdirectory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / 'pyproject.toml').write_text('[project]\nname = "x"\n')
            sub = root / 'a' / 'b' / 'c'
            sub.mkdir(parents=True)
            config = load_config(sub)
        self.assertEqual(config.project_root, root.resolve())

    def test_non_list_value_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / 'pyproject.toml').write_text(
                textwrap.dedent("""
                    [tool.assertions.discovery]
                    include_paths = "tests/"
                """).lstrip()
            )
            with self.assertRaises(ConfigurationError) as ctx:
                load_config(root)
        self.assertIn('include_paths', str(ctx.exception))

    def test_list_with_non_string_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / 'pyproject.toml').write_text(
                textwrap.dedent("""
                    [tool.assertions.discovery]
                    test_files = ["test_*.py", 42]
                """).lstrip()
            )
            with self.assertRaises(ConfigurationError) as ctx:
                load_config(root)
        self.assertIn('test_files', str(ctx.exception))

    def test_unknown_key_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / 'pyproject.toml').write_text(
                textwrap.dedent("""
                    [tool.assertions.discovery]
                    include_paths = ["tests/**"]
                    typoed_key = ["nope"]
                """).lstrip()
            )
            with self.assertRaises(ConfigurationError) as ctx:
                load_config(root)
        self.assertIn('typoed_key', str(ctx.exception))


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run the tests; they fail on import**

Run:
```bash
uv run python -m unittest tests.test_config -v
```

Expected: `ImportError: cannot import name 'ConfigurationError' from 'assertions'` or `ModuleNotFoundError: No module named 'assertions._config'`.

- [ ] **Step 3: Create `src/assertions/_config.py`**

```python
import pathlib
import tomllib
from dataclasses import dataclass, field


_VALID_KEYS = frozenset(
    {'include_paths', 'exclude_paths', 'test_files'}
)


class ConfigurationError(Exception):
    pass


@dataclass(frozen=True)
class DiscoveryConfig:
    include_paths: tuple[str, ...] = field(default=())
    exclude_paths: tuple[str, ...] = field(default=())
    test_files: tuple[str, ...] = field(default=())
    project_root: pathlib.Path | None = field(default=None)


def load_config(start: pathlib.Path) -> DiscoveryConfig:
    pyproject = _find_pyproject(start)
    if pyproject is None:
        return DiscoveryConfig()
    project_root = pyproject.parent.resolve()
    raw = tomllib.loads(pyproject.read_text())
    section = (
        raw.get('tool', {}).get('assertions', {}).get('discovery', {})
    )
    return _build_config(section, project_root)


def _find_pyproject(start: pathlib.Path) -> pathlib.Path | None:
    current = start.resolve()
    while True:
        candidate = current / 'pyproject.toml'
        if candidate.exists():
            return candidate
        if current.parent == current:
            return None
        current = current.parent


def _build_config(
    section: dict,
    project_root: pathlib.Path,
) -> DiscoveryConfig:
    unknown = set(section) - _VALID_KEYS
    if unknown:
        raise ConfigurationError(
            f'unknown key {sorted(unknown)[0]!r} in '
            f'[tool.assertions.discovery]'
        )
    return DiscoveryConfig(
        include_paths=_to_string_tuple(
            section.get('include_paths', []), 'include_paths',
        ),
        exclude_paths=_to_string_tuple(
            section.get('exclude_paths', []), 'exclude_paths',
        ),
        test_files=_to_string_tuple(
            section.get('test_files', []), 'test_files',
        ),
        project_root=project_root,
    )


def _to_string_tuple(value: object, key: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ConfigurationError(
            f'tool.assertions.discovery.{key} must be a list of strings'
        )
    for item in value:
        if not isinstance(item, str):
            raise ConfigurationError(
                f'tool.assertions.discovery.{key} must be a list of strings'
            )
    return tuple(value)
```

- [ ] **Step 4: Re-export `ConfigurationError` from the package**

Replace the contents of `src/assertions/__init__.py` with:

```python
from assertions._catches import catch_exceptions, catch_warnings
from assertions._config import ConfigurationError
from assertions._discover import discover
from assertions._markers import test
from assertions._params import test_params, test_params_lazy
from assertions._runner import run
from assertions._test_class import Test

__all__ = [
    'ConfigurationError',
    'Test',
    'catch_exceptions',
    'catch_warnings',
    'discover',
    'run',
    'test',
    'test_params',
    'test_params_lazy',
]
```

- [ ] **Step 5: Run the tests; they pass**

Run:
```bash
uv run python -m unittest tests.test_config -v
```

Expected: 7 tests pass.

- [ ] **Step 6: Run the full suite to confirm no regressions**

Run:
```bash
uv run python -m unittest discover -s tests -v 2>&1 | tail -10
```

Expected: every existing test passes; the new config tests are included.

- [ ] **Step 7: Run mypy**

Run:
```bash
uv run mypy
```

Expected: `Success: no issues found`.

- [ ] **Step 8: Commit**

```bash
git add src/assertions/_config.py src/assertions/__init__.py tests/test_config.py
git commit -m "Add DiscoveryConfig and load_config from pyproject.toml"
```

---

## Task 2: Extract `_exec_module_from_path` helper

**Files:**
- Modify: `src/assertions/_targets.py`
- Modify: `tests/test_targets.py`

This task removes the four-line duplication between `_load_path` and the fallback branch of `_load_path_for_walk` without changing any behavior.

- [ ] **Step 1: Append a unit test for the helper to `tests/test_targets.py`**

Add (before `if __name__ == '__main__':`):

```python
class TestExecModuleFromPath(unittest.TestCase):
    def test_loads_a_simple_module(self):
        from assertions._targets import _exec_module_from_path

        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / 'demo.py'
            path.write_text('value = 42\n')
            module = _exec_module_from_path(path)
        self.assertEqual(getattr(module, 'value'), 42)
        self.assertEqual(module.__name__, 'demo')

    def test_unloadable_path_raises_import_error(self):
        from assertions._targets import _exec_module_from_path

        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / 'missing.py'
            with self.assertRaises((ImportError, FileNotFoundError)):
                _exec_module_from_path(path)
```

- [ ] **Step 2: Run the new tests; they fail**

Run:
```bash
uv run python -m unittest tests.test_targets.TestExecModuleFromPath -v
```

Expected: `ImportError: cannot import name '_exec_module_from_path'`.

- [ ] **Step 3: Update `src/assertions/_targets.py`**

Replace `_load_path` and the fallback inside `_load_path_for_walk` to call a new helper. The full updated section:

```python
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
```

- [ ] **Step 4: Run the new tests; they pass**

Run:
```bash
uv run python -m unittest tests.test_targets.TestExecModuleFromPath -v
```

Expected: 2 tests pass.

- [ ] **Step 5: Run the full suite**

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
git add src/assertions/_targets.py tests/test_targets.py
git commit -m "Extract _exec_module_from_path helper"
```

---

## Task 3: Refactor `_walk_directory` to use `os.scandir`

**Files:**
- Modify: `src/assertions/_targets.py`

Pure refactor. Existing `_walk_directory` tests verify behavior, including the depth-first alphabetical order. After this change they all still pass.

- [ ] **Step 1: Replace the `_walk_directory` function in `src/assertions/_targets.py`**

```python
def _walk_directory(root: pathlib.Path) -> list[pathlib.Path]:
    out: list[pathlib.Path] = []
    with os.scandir(root) as it:
        entries = sorted(it, key=lambda e: e.name)
    for entry in entries:
        if entry.is_dir(follow_symlinks=False):
            if _is_excluded_dir(entry.name):
                continue
            out.extend(_walk_directory(pathlib.Path(entry.path)))
        elif entry.is_file(follow_symlinks=False) and entry.name.endswith(
            '.py'
        ):
            out.append(pathlib.Path(entry.path))
    return out
```

- [ ] **Step 2: Run the existing walker tests; they pass**

Run:
```bash
uv run python -m unittest tests.test_targets.TestWalkDirectory -v
```

Expected: 6 tests pass.

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
git commit -m "Refactor _walk_directory to use os.scandir"
```

---

## Task 4: Add failing tests for config-aware walking

**Files:**
- Modify: `tests/test_targets.py`

These tests describe the new behavior of `_walk_directory` once it accepts a `config` and `excluded` set. The implementation lands in Task 5.

- [ ] **Step 1: Append a new test class to `tests/test_targets.py`**

Add (before `if __name__ == '__main__':`):

```python
class TestWalkDirectoryWithConfig(unittest.TestCase):
    def test_test_files_filter_keeps_matching_names(self):
        from assertions._config import DiscoveryConfig
        from assertions._targets import _walk_directory

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
        from assertions._targets import _walk_directory

        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / 'helper.py').write_text('')
            config = DiscoveryConfig(test_files=('test_*.py',))
            paths = _walk_directory(root, config=config, excluded=set())
        self.assertEqual(paths, [])

    def test_excluded_set_drops_files(self):
        from assertions._config import DiscoveryConfig
        from assertions._targets import _walk_directory

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
        from assertions._targets import _walk_directory

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
        from assertions._targets import _walk_directory

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
```

- [ ] **Step 2: Run the new tests; they fail**

Run:
```bash
uv run python -m unittest tests.test_targets.TestWalkDirectoryWithConfig -v
```

Expected: every test fails. The current `_walk_directory` does not accept a `config` keyword argument, so each test fails with `TypeError: _walk_directory() got an unexpected keyword argument 'config'`. The `test_default_args_preserve_old_behavior` test passes (today's signature accepts no extra args).

- [ ] **Step 3: Commit**

```bash
git add tests/test_targets.py
git commit -m "Add failing tests for config-aware walker"
```

---

## Task 5: Implement config-aware `_walk_directory`

**Files:**
- Modify: `src/assertions/_targets.py`

- [ ] **Step 1: Update `_walk_directory` to accept `config` and `excluded`**

Replace the function with:

```python
def _walk_directory(
    root: pathlib.Path,
    config: 'DiscoveryConfig | None' = None,
    excluded: set[pathlib.Path] | None = None,
) -> list[pathlib.Path]:
    out: list[pathlib.Path] = []
    with os.scandir(root) as it:
        entries = sorted(it, key=lambda e: e.name)
    for entry in entries:
        if entry.is_dir(follow_symlinks=False):
            if _is_excluded_dir(entry.name):
                continue
            out.extend(
                _walk_directory(
                    pathlib.Path(entry.path),
                    config=config,
                    excluded=excluded,
                )
            )
        elif entry.is_file(follow_symlinks=False) and entry.name.endswith(
            '.py'
        ):
            path = pathlib.Path(entry.path)
            if not _accepts_file(path, config, excluded):
                continue
            out.append(path)
    return out


def _accepts_file(
    path: pathlib.Path,
    config: 'DiscoveryConfig | None',
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
```

- [ ] **Step 2: Add the `fnmatch` import to the top of `_targets.py`**

Add `import fnmatch` to the import block (alphabetical: between `import importlib.util` and `import os`).

- [ ] **Step 3: Add the forward-reference resolution by importing `DiscoveryConfig`**

Add the following import at the top of `_targets.py` after the `from types import ModuleType` line:

```python
from assertions._config import DiscoveryConfig
```

Then change the type hints in `_walk_directory` and `_accepts_file` from the string `'DiscoveryConfig | None'` to the bare `DiscoveryConfig | None`.

- [ ] **Step 4: Run the new tests; they pass**

Run:
```bash
uv run python -m unittest tests.test_targets.TestWalkDirectoryWithConfig -v
```

Expected: 5 tests pass.

- [ ] **Step 5: Run the full suite**

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
git add src/assertions/_targets.py
git commit -m "Apply test_files and excluded filters in _walk_directory"
```

---

## Task 6: Wire config through `parse_target` and the CLI

**Files:**
- Modify: `src/assertions/_targets.py`
- Modify: `src/assertions/__main__.py`

`parse_target` and `__main__.main` both need to know about config. The existing single-arg `parse_target(target)` keeps working (config defaults to `None`); the CLI adds an explicit pass.

- [ ] **Step 1: Update `parse_target` to accept config and excluded**

Modify the function in `_targets.py`:

```python
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
                    path, config=config, excluded=excluded,
                )
            ]
        return [(_load_path(target), None)]
    return [_resolve_dotted(target)]
```

- [ ] **Step 2: Add `_resolve_include_paths` and `_build_exclude_set` to `_targets.py`**

```python
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

- [ ] **Step 3: Update `__main__.py` to use config**

Replace its contents with:

```python
import pathlib
import sys
from types import ModuleType

from assertions._config import DiscoveryConfig, load_config
from assertions._runner import run
from assertions._targets import (
    _build_exclude_set,
    _load_path_for_walk,
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
                    print(
                        f'{name} ... FAIL: {type(exc).__name__}: {exc}'
                    )
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
                root, config=config, excluded=excluded,
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
```

- [ ] **Step 4: Run the full suite to confirm no regressions**

Run:
```bash
uv run python -m unittest discover -s tests -v 2>&1 | tail -10
```

Expected: every existing test still passes (no new tests yet).

- [ ] **Step 5: Run mypy**

Run:
```bash
uv run mypy
```

Expected: `Success: no issues found`.

- [ ] **Step 6: Commit**

```bash
git add src/assertions/_targets.py src/assertions/__main__.py
git commit -m "Thread DiscoveryConfig through parse_target and main"
```

---

## Task 7: Add CLI tests for config-driven discovery

**Files:**
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Append test methods to the existing `class TestCli(unittest.TestCase):` body**

Add (before `if __name__ == '__main__':`):

```python
    def _make_test_module(self, root, name, body):
        import textwrap

        (root / name).write_text(
            textwrap.dedent(body).lstrip()
        )

    def _passing_test(self, func_name='passes'):
        return f"""
            from assertions import test

            @test
            def {func_name}():
                assert True
        """

    def test_config_include_paths_narrows_walk(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            sub = root / 'sub'
            sub.mkdir()
            other = root / 'other'
            other.mkdir()
            self._make_test_module(
                sub, 'test_in_sub.py', self._passing_test('in_sub'),
            )
            self._make_test_module(
                other, 'test_in_other.py',
                self._passing_test('in_other'),
            )
            (root / 'pyproject.toml').write_text(
                '[tool.assertions.discovery]\n'
                'include_paths = ["sub/**"]\n'
            )
            result = subprocess.run(
                [sys.executable, '-m', 'assertions'],
                capture_output=True,
                text=True,
                cwd=tmp,
            )
        self.assertEqual(result.returncode, 0)
        self.assertIn('in_sub ... ok', result.stdout)
        self.assertNotIn('in_other', result.stdout)

    def test_config_exclude_paths_drops_matches(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            self._make_test_module(
                root, 'test_keep.py', self._passing_test('keep'),
            )
            vendored = root / 'vendored'
            vendored.mkdir()
            self._make_test_module(
                vendored, 'test_drop.py',
                self._passing_test('drop'),
            )
            (root / 'pyproject.toml').write_text(
                '[tool.assertions.discovery]\n'
                'exclude_paths = ["vendored/**"]\n'
            )
            result = subprocess.run(
                [sys.executable, '-m', 'assertions'],
                capture_output=True,
                text=True,
                cwd=tmp,
            )
        self.assertEqual(result.returncode, 0)
        self.assertIn('keep ... ok', result.stdout)
        self.assertNotIn('drop', result.stdout)

    def test_config_test_files_filters_filenames(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            self._make_test_module(
                root, 'test_match.py',
                self._passing_test('matched'),
            )
            self._make_test_module(
                root, 'helper.py',
                self._passing_test('skipped'),
            )
            (root / 'pyproject.toml').write_text(
                '[tool.assertions.discovery]\n'
                'test_files = ["test_*.py"]\n'
            )
            result = subprocess.run(
                [sys.executable, '-m', 'assertions'],
                capture_output=True,
                text=True,
                cwd=tmp,
            )
        self.assertEqual(result.returncode, 0)
        self.assertIn('matched ... ok', result.stdout)
        self.assertNotIn('skipped', result.stdout)

    def test_argv_directory_ignores_include_paths(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            sub = root / 'sub'
            sub.mkdir()
            other = root / 'other'
            other.mkdir()
            self._make_test_module(
                sub, 'test_in_sub.py',
                self._passing_test('in_sub'),
            )
            self._make_test_module(
                other, 'test_in_other.py',
                self._passing_test('in_other'),
            )
            (root / 'pyproject.toml').write_text(
                '[tool.assertions.discovery]\n'
                'include_paths = ["sub/**"]\n'
            )
            result = subprocess.run(
                [sys.executable, '-m', 'assertions', 'other'],
                capture_output=True,
                text=True,
                cwd=tmp,
            )
        self.assertEqual(result.returncode, 0)
        self.assertIn('in_other ... ok', result.stdout)
        self.assertNotIn('in_sub', result.stdout)

    def test_argv_directory_still_honors_exclude_paths(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            src = root / 'src'
            src.mkdir()
            self._make_test_module(
                src, 'test_keep.py',
                self._passing_test('keep'),
            )
            vendored = src / 'vendored'
            vendored.mkdir()
            self._make_test_module(
                vendored, 'test_drop.py',
                self._passing_test('drop'),
            )
            (root / 'pyproject.toml').write_text(
                '[tool.assertions.discovery]\n'
                'exclude_paths = ["src/vendored/**"]\n'
            )
            result = subprocess.run(
                [sys.executable, '-m', 'assertions', 'src'],
                capture_output=True,
                text=True,
                cwd=tmp,
            )
        self.assertEqual(result.returncode, 0)
        self.assertIn('keep ... ok', result.stdout)
        self.assertNotIn('drop', result.stdout)

    def test_invalid_config_raises_configuration_error(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            self._make_test_module(
                root, 'test_a.py', self._passing_test('a'),
            )
            (root / 'pyproject.toml').write_text(
                '[tool.assertions.discovery]\n'
                'typoed_key = ["nope"]\n'
            )
            result = subprocess.run(
                [sys.executable, '-m', 'assertions'],
                capture_output=True,
                text=True,
                cwd=tmp,
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('ConfigurationError', result.stderr)
        self.assertIn('typoed_key', result.stderr)
```

- [ ] **Step 2: Run the new tests; they pass**

Run:
```bash
uv run python -m unittest tests.test_cli -v
```

Expected: every CLI test passes (existing 13 + 6 new = 19).

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
git add tests/test_cli.py
git commit -m "Add CLI tests for pyproject.toml discovery config"
```

---

## Task 8: Smoke-test the config-driven CLI

**Files:** none — verification only.

- [ ] **Step 1: include_paths narrows the walk**

Run:
```bash
uv run python -c "
import pathlib, subprocess, sys, tempfile, textwrap
with tempfile.TemporaryDirectory() as tmp:
    root = pathlib.Path(tmp)
    (root / 'pyproject.toml').write_text(
        '[tool.assertions.discovery]\n'
        'include_paths = [\"good/**\"]\n'
    )
    good = root / 'good'
    good.mkdir()
    (good / 'test_a.py').write_text(textwrap.dedent('''
        from assertions import test
        @test
        def included():
            assert True
    ''').lstrip())
    bad = root / 'bad'
    bad.mkdir()
    (bad / 'test_b.py').write_text(textwrap.dedent('''
        from assertions import test
        @test
        def not_included():
            raise AssertionError(\"should not run\")
    ''').lstrip())
    r = subprocess.run([sys.executable, '-m', 'assertions'], cwd=tmp, capture_output=True, text=True)
    print('exit:', r.returncode)
    print('stdout:', r.stdout)
    print('stderr:', r.stderr)
"
```

Expected: `exit: 0`, stdout contains `included ... ok`, no `not_included`.

- [ ] **Step 2: invalid config raises ConfigurationError**

Run:
```bash
uv run python -c "
import pathlib, subprocess, sys, tempfile
with tempfile.TemporaryDirectory() as tmp:
    root = pathlib.Path(tmp)
    (root / 'pyproject.toml').write_text(
        '[tool.assertions.discovery]\n'
        'oops = []\n'
    )
    r = subprocess.run([sys.executable, '-m', 'assertions'], cwd=tmp, capture_output=True, text=True)
    print('exit:', r.returncode)
    print('stderr:', r.stderr)
"
```

Expected: non-zero exit, stderr contains `ConfigurationError` and `oops`.

- [ ] **Step 3: existing examples still pass**

Run:
```bash
uv run python -m assertions examples.functions; echo "exit=$?"
uv run python -m assertions examples.classes; echo "exit=$?"
uv run python -m assertions examples.catches; echo "exit=$?"
```

Expected: all three exit 0.

- [ ] **Step 4: existing CLI surface still works**

Run:
```bash
uv run python -m assertions tests/fixtures/runner/all_pass.py; echo "exit=$?"
uv run python -m assertions tests.fixtures.runner.class_simple.Simple.first; echo "exit=$?"
```

Expected: both exit 0.

- [ ] **Step 5: No commit**

If any smoke step fails, return to the relevant earlier task and diagnose.

---

## Self-Review

- **Spec coverage:**
  - `[tool.assertions.discovery]` schema (`include_paths`, `exclude_paths`, `test_files`) — Task 1 ✓
  - `ConfigurationError` raised on unknown keys and wrong types — Task 1 tests 5-7 ✓
  - Walk-up to find `pyproject.toml` — Task 1 test 4 ✓
  - Empty config when no pyproject — Task 1 test 1 ✓
  - `_walk_directory` accepts `config` and `excluded` — Task 5 ✓
  - `test_files` matches via `fnmatch` — Task 4 tests 1-2 ✓
  - `excluded` set drops files — Task 4 test 3 ✓
  - Default args preserve old behavior — Task 4 test 4 ✓
  - `include_paths` resolved via `Path.glob` — Task 6 `_resolve_include_paths` ✓
  - Exclude set pre-computed via `Path.glob` — Task 6 `_build_exclude_set` ✓
  - Argv directory targets ignore `include_paths` — Task 7 test 4 ✓
  - Argv directory targets still honor `exclude_paths` and `test_files` — Task 7 test 5 ✓
  - CLI errors propagate `ConfigurationError` — Task 7 test 6 ✓
  - `_walk_directory` uses `os.scandir` — Task 3 ✓
  - `_exec_module_from_path` extracted, both loaders use it — Task 2 ✓
  - mypy clean — Tasks 1, 2, 3, 5, 6, 7 ✓
  - Examples still pass — Task 8 step 3 ✓
- **Placeholder scan:** none.
- **Type consistency:**
  - `DiscoveryConfig` fields: `tuple[str, ...]` and `pathlib.Path | None` consistently across `_config.py` and consumers.
  - `_walk_directory(root, config=None, excluded=None)` — same signature in Task 5 implementation and Task 6 caller (`parse_target`).
  - `_resolve_include_paths` returns `list[pathlib.Path]`; `_build_exclude_set` returns `set[pathlib.Path]`. Both consumed in `__main__.main`.
  - `parse_target(target, config, excluded)` signature matches between `_targets.py` and `__main__.py`.
  - `ConfigurationError` re-exported from `__init__.py` so users (and tests) can `from assertions import ConfigurationError`.
