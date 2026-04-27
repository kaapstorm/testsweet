# `discover_targets` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Run Python via uv:** All Python invocations use `uv run python ...` (or `uv run mypy`). Never call `python` or `mypy` directly.
>
> **Code style:** ruff-format runs as a pre-commit hook (`quote-style = 'single'`, `line-length = 79`). Use single quotes in new files. If a commit is rejected because the hook reformatted files, re-stage and commit again.

**Goal:** Replace `__main__.py`'s five private imports across three modules with one call to `discover_targets(argv, config)` in `_targets.py`. Move `_bare_invocation` and `_add_to_groups` alongside it. Add direct unit tests for `discover_targets`.

**Architecture:** The CLI's existing logic is split into two parts: discovery (turn argv + config into a list of `(module, names)` pairs) and execution (run, print, exit). Discovery moves wholesale into `_targets.py` as `discover_targets`. The CLI keeps execution. Behavior is frozen — same units run, same output, same exit codes.

**Tech Stack:** Python ≥3.11, `uv`, standard library only.

---

## File Structure

| Path | Action | Purpose |
|------|--------|---------|
| `src/assertions/_targets.py` | modify | Add `discover_targets`, `_bare_invocation`, `_add_to_groups`; gain imports from `_walk`, `_loaders` |
| `src/assertions/__main__.py` | modify | Drop `_bare_invocation`, `_add_to_groups`; reduce imports to three; call `discover_targets` |
| `tests/test_targets.py` | modify | Add `TestDiscoverTargets` |

No new files, no deletions.

---

## Task 1: Add `discover_targets`, `_bare_invocation`, `_add_to_groups` to `_targets.py`

**Files:**
- Modify: `src/assertions/_targets.py`

In this task, we ADD the new functions to `_targets.py` without removing them from `__main__.py` yet. After this task, `_bare_invocation` and `_add_to_groups` exist in both files (CLI still uses its own). The duplication is removed in Task 2 to keep each commit verifiable.

- [ ] **Step 1: Update `src/assertions/_targets.py` to its final form**

Replace the entire contents:

```python
import pathlib
from types import ModuleType

from assertions._classify import _resolve_dotted
from assertions._config import DiscoveryConfig
from assertions._loaders import _load_path, _load_path_for_walk
from assertions._walk import (
    _build_exclude_set,
    _resolve_include_paths,
    _walk_directory,
)


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
```

- [ ] **Step 2: Run the full test suite**

Run:
```bash
uv run python -m unittest discover -s tests -v 2>&1 | tail -10
```

Expected: every test passes. The CLI still uses its own copy of
`_bare_invocation` and `_add_to_groups`; no behavior change yet.

- [ ] **Step 3: Run mypy**

Run:
```bash
uv run mypy
```

Expected: `Success: no issues found`.

- [ ] **Step 4: Commit**

```bash
git add src/assertions/_targets.py
git commit -m "Add discover_targets to _targets.py"
```

---

## Task 2: Slim `__main__.py` to call `discover_targets`

**Files:**
- Modify: `src/assertions/__main__.py`

- [ ] **Step 1: Replace the entire contents of `src/assertions/__main__.py`**

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

Confirm what was removed: the `from types import ModuleType` import,
the `from assertions._loaders import _load_path_for_walk` import,
the `from assertions._targets import parse_target` import (replaced),
the `from assertions._walk import (_build_exclude_set,
_resolve_include_paths, _walk_directory)` block, the
`_bare_invocation` function, the `_add_to_groups` function, and the
intermediate `excluded`, `argv_groups`, and `groups` variables in
`main`.

- [ ] **Step 2: Run the full test suite**

Run:
```bash
uv run python -m unittest discover -s tests -v 2>&1 | tail -10
```

Expected: every test passes (the CLI tests cover the same paths
end-to-end; behavior is unchanged).

- [ ] **Step 3: Run mypy**

Run:
```bash
uv run mypy
```

Expected: `Success: no issues found`.

- [ ] **Step 4: Confirm `__main__.py` import shape**

Run:
```bash
grep -n '^from\|^import' src/assertions/__main__.py
```

Expected output (in order):

```
import pathlib
import sys
from assertions._config import load_config
from assertions._runner import run
from assertions._targets import discover_targets
```

Five import lines total. No other `from assertions._` imports.

- [ ] **Step 5: Commit**

```bash
git add src/assertions/__main__.py
git commit -m "CLI calls discover_targets; drop direct imports of discovery helpers"
```

---

## Task 3: Add `TestDiscoverTargets` to `tests/test_targets.py`

**Files:**
- Modify: `tests/test_targets.py`

This task adds direct unit tests for `discover_targets`. Most CLI
scenarios are already covered end-to-end by `tests/test_cli.py`; the
new tests give us faster, simpler coverage and document the contract.

- [ ] **Step 1: Add the import to the top of `tests/test_targets.py`**

Append `discover_targets` to the existing
`from assertions._targets import parse_target` line so it reads:

```python
from assertions._targets import discover_targets, parse_target
```

- [ ] **Step 2: Append a new test class to `tests/test_targets.py`**

Add the following block before the trailing `if __name__ == '__main__':`:

```python
class TestDiscoverTargets(unittest.TestCase):
    # discover_targets imports test modules from temp directories,
    # which leaves entries in sys.modules. Snapshot/restore so
    # short-lived tmp-dir module names don't leak between tests.

    def setUp(self):
        import sys

        self._saved_modules = dict(sys.modules)

    def tearDown(self):
        import sys

        for name in list(sys.modules):
            if name not in self._saved_modules:
                del sys.modules[name]

    def test_single_dotted_module(self):
        from assertions._config import DiscoveryConfig

        config = DiscoveryConfig()
        groups = discover_targets(
            ['tests.fixtures.runner.all_pass'],
            config,
        )
        self.assertEqual(len(groups), 1)
        module, names = groups[0]
        expected = importlib.import_module(
            'tests.fixtures.runner.all_pass',
        )
        self.assertIs(module, expected)
        self.assertIsNone(names)

    def test_single_selector_returns_module_with_names(self):
        from assertions._config import DiscoveryConfig

        config = DiscoveryConfig()
        groups = discover_targets(
            ['tests.fixtures.runner.class_simple.Simple.first'],
            config,
        )
        self.assertEqual(len(groups), 1)
        module, names = groups[0]
        expected = importlib.import_module(
            'tests.fixtures.runner.class_simple',
        )
        self.assertIs(module, expected)
        self.assertEqual(names, ['Simple.first'])

    def test_two_distinct_modules(self):
        from assertions._config import DiscoveryConfig

        config = DiscoveryConfig()
        groups = discover_targets(
            [
                'tests.fixtures.runner.all_pass',
                'tests.fixtures.runner.has_failure',
            ],
            config,
        )
        self.assertEqual(len(groups), 2)
        self.assertEqual(
            groups[0][0].__name__,
            'tests.fixtures.runner.all_pass',
        )
        self.assertEqual(
            groups[1][0].__name__,
            'tests.fixtures.runner.has_failure',
        )

    def test_duplicate_module_deduped(self):
        from assertions._config import DiscoveryConfig

        config = DiscoveryConfig()
        groups = discover_targets(
            [
                'tests.fixtures.runner.all_pass',
                'tests.fixtures.runner.all_pass',
            ],
            config,
        )
        self.assertEqual(len(groups), 1)
        _, names = groups[0]
        self.assertIsNone(names)

    def test_module_then_selector_for_same_module_keeps_module(self):
        from assertions._config import DiscoveryConfig

        config = DiscoveryConfig()
        groups = discover_targets(
            [
                'tests.fixtures.runner.all_pass',
                'tests.fixtures.runner.all_pass.passes_one',
            ],
            config,
        )
        self.assertEqual(len(groups), 1)
        _, names = groups[0]
        self.assertIsNone(names)

    def test_two_selectors_same_module_merge_names(self):
        from assertions._config import DiscoveryConfig

        config = DiscoveryConfig()
        groups = discover_targets(
            [
                'tests.fixtures.runner.class_simple.Simple.first',
                'tests.fixtures.runner.class_simple.Simple.second',
            ],
            config,
        )
        self.assertEqual(len(groups), 1)
        _, names = groups[0]
        self.assertEqual(names, ['Simple.first', 'Simple.second'])

    def test_directory_argv_yields_one_entry_per_py_file(self):
        from assertions._config import DiscoveryConfig

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
            config = DiscoveryConfig()
            groups = discover_targets([str(root)], config)
        self.assertEqual(len(groups), 2)
        for _, names in groups:
            self.assertIsNone(names)

    def test_bare_invocation_with_include_paths(self):
        from assertions._config import DiscoveryConfig

        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp).resolve()
            sub = root / 'sub'
            sub.mkdir()
            (sub / 'in_sub.py').write_text(
                'from assertions import test\n'
                '@test\n'
                'def in_sub():\n'
                '    pass\n'
            )
            other = root / 'other'
            other.mkdir()
            (other / 'in_other.py').write_text(
                'from assertions import test\n'
                '@test\n'
                'def in_other():\n'
                '    pass\n'
            )
            config = DiscoveryConfig(
                include_paths=('sub/**',),
                project_root=root,
            )
            groups = discover_targets([], config)
        names_seen = sorted(
            getattr(module, '__name__', '') for module, _ in groups
        )
        self.assertTrue(
            any('in_sub' in n for n in names_seen),
            msg=f'expected sub/ module; got {names_seen}',
        )
        self.assertFalse(
            any('in_other' in n for n in names_seen),
            msg=f'unexpected other/ module; got {names_seen}',
        )

    def test_bare_invocation_walks_cwd_when_no_include_paths(self):
        # discover_targets reads cwd via pathlib.Path('.').resolve()
        # inside _bare_invocation. Use os.chdir to point cwd at a
        # tmp tree with one test module, restoring afterwards.
        from assertions._config import DiscoveryConfig

        config = DiscoveryConfig()
        original_cwd = pathlib.Path.cwd()
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp).resolve()
            (root / 'cwd_test.py').write_text(
                'from assertions import test\n'
                '@test\n'
                'def from_cwd():\n'
                '    pass\n'
            )
            os.chdir(root)
            try:
                groups = discover_targets([], config)
            finally:
                os.chdir(original_cwd)
        self.assertEqual(len(groups), 1)
        module, names = groups[0]
        self.assertIsNone(names)
        self.assertTrue(hasattr(module, 'from_cwd'))
```

- [ ] **Step 3: Run the new tests; they pass**

Run:
```bash
uv run python -m unittest tests.test_targets.TestDiscoverTargets -v
```

Expected: 9 tests pass.

- [ ] **Step 4: Run the full suite to confirm no regressions**

Run:
```bash
uv run python -m unittest discover -s tests -v 2>&1 | tail -10
```

Expected: every test passes; total count is 145 (previous 136 + 9
new).

- [ ] **Step 5: Run mypy**

Run:
```bash
uv run mypy
```

Expected: `Success: no issues found`.

- [ ] **Step 6: Commit**

```bash
git add tests/test_targets.py
git commit -m "Add direct tests for discover_targets"
```

---

## Task 4: Smoke-test the refactor

**Files:** none — verification only.

- [ ] **Step 1: existing CLI surface still works**

Run:
```bash
uv run python -m assertions tests/fixtures/runner/all_pass.py; echo "exit=$?"
uv run python -m assertions tests.fixtures.runner.class_simple.Simple.first; echo "exit=$?"
```

Expected: both exit 0 with appropriate output (file path: two
`... ok` lines; selector: one `Simple.first ... ok` line).

- [ ] **Step 2: multi-target argv works**

Run:
```bash
uv run python -m assertions tests.fixtures.runner.all_pass tests.fixtures.runner.has_failure; echo "exit=$?"
```

Expected: lines from `all_pass` (`passes_one`, `passes_two`), then
`has_failure` (`passes`, `fails ... FAIL: AssertionError`); exit 1.

- [ ] **Step 3: bare invocation with no config**

Run inside a tmp tree with one test:

```bash
uv run python -c "
import pathlib, subprocess, sys, tempfile, textwrap
with tempfile.TemporaryDirectory() as tmp:
    (pathlib.Path(tmp) / 'test_x.py').write_text(textwrap.dedent('''
        from assertions import test
        @test
        def hit():
            assert True
    ''').lstrip())
    r = subprocess.run([sys.executable, '-m', 'assertions'], cwd=tmp, capture_output=True, text=True)
    print('exit:', r.returncode)
    print('stdout:', r.stdout)
"
```

Expected: `exit: 0`, stdout contains `hit ... ok`.

- [ ] **Step 4: confirm __main__.py shape**

Run:
```bash
wc -l src/assertions/__main__.py
```

Expected: ~28 lines.

Run:
```bash
grep -n 'from assertions' src/assertions/__main__.py
```

Expected exactly three lines: `_config`, `_runner`, `_targets`. No
imports from `_loaders` or `_walk`.

- [ ] **Step 5: No commit**

If any smoke step fails, return to the relevant earlier task and
diagnose.

---

## Self-Review

- **Spec coverage:**
  - `discover_targets(argv, config)` defined in `_targets.py` — Task 1 ✓
  - Behavior: bare → `_bare_invocation`; argv → `parse_target` per
    arg; merge by `_add_to_groups` — Task 1 implementation ✓
  - `_bare_invocation` + `_add_to_groups` move to `_targets.py` —
    Task 1 (added) + Task 2 (removed from `__main__.py`) ✓
  - `__main__.py` imports drop to three — Task 2 step 4 ✓
  - `__main__.py` calls `discover_targets` — Task 2 step 1 ✓
  - Single dotted module test — Task 3 test 1 ✓
  - Selector test — Task 3 test 2 ✓
  - Two distinct modules — Task 3 test 3 ✓
  - Duplicate module deduped — Task 3 test 4 ✓
  - Whole-module wins over selector — Task 3 test 5 ✓
  - Two selectors merge — Task 3 test 6 ✓
  - Directory argv — Task 3 test 7 ✓
  - Bare with `include_paths` — Task 3 test 8 ✓
  - Bare walks cwd — Task 3 test 9 ✓
  - Existing CLI tests still pass — Tasks 2, 3 step 4, Task 4 ✓
  - mypy clean — Tasks 1, 2, 3 ✓
- **Placeholder scan:** none.
- **Type consistency:**
  - `discover_targets(argv: list[str], config: DiscoveryConfig)
    -> list[tuple[ModuleType, list[str] | None]]` matches between
    Task 1 implementation and Task 2 caller.
  - `_bare_invocation` and `_add_to_groups` signatures unchanged
    from their pre-move forms — Task 1 copies them verbatim from
    `__main__.py`.
  - The new `TestDiscoverTargets` setUp/tearDown follows the same
    sys.modules snapshot pattern used by `TestParseTargetDirectory`
    in the same file.
