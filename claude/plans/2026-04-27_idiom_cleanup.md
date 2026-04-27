# Idiom-Level Cleanups Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Run Python via uv:** All Python invocations use `uv run python ...` (or `uv run mypy`). Never call `python` or `mypy` directly.
>
> **Code style:** ruff-format runs as a pre-commit hook (`quote-style = 'single'`, `line-length = 79`). Use single quotes in new files. If a commit is rejected because the hook reformatted files, re-stage and commit again.

**Goal:** Four small idiom-level cleanups: tighten `_dotted_name_for_path`'s return shape; rewrite `_resolve_dotted` with a `range`-based loop and a named helper; replace `_add_to_groups`'s O(n²) merge with an O(n) dict-based one inside `discover_targets`; flatten `resolve_units` from `list[Iterator]` to a single `Iterator`.

**Architecture:** Each cleanup stands alone. They land as four separate tasks, in the order (b → a → d → e), so each commit's diff is small and the test suite confirms behavior at every checkpoint. (b) is the most contained (no callers change). (a) updates one caller in `_loaders.py`. (d) replaces an internal helper. (e) touches both `_resolve.py` and `_runner.py` and is left for last to avoid re-touching the runner mid-refactor.

**Tech Stack:** Python ≥3.11, `uv`, standard library only.

---

## File Structure

| Path | Action | Purpose |
|------|--------|---------|
| `src/assertions/_classify.py` | rewrite | `_resolve_dotted` (b) + `_is_missing_prefix_error` helper |
| `src/assertions/_loaders.py` | modify | `_dotted_name_for_path` return shape (a); `_load_path_for_walk` adapts |
| `src/assertions/_targets.py` | modify | `discover_targets` does dict-based merge (d); `_add_to_groups` removed |
| `src/assertions/_resolve.py` | modify | `resolve_units` flattens (e) |
| `src/assertions/_runner.py` | modify | single for-loop (e) |
| `tests/test_loaders.py` | modify | `_dotted_name_for_path` tests adapt to `tuple | None` (a) |
| `tests/test_resolve.py` | modify | iteration-shape updates (e) |

No new files. No tests added or removed; existing tests are updated to match the new return shapes.

---

## Task 1: Rewrite `_resolve_dotted` (b)

**Files:**
- Modify: `src/assertions/_classify.py`

`_resolve_dotted` has no callers that need to change — it returns the same `tuple[ModuleType, list[str] | None]`. The rewrite is internal: replace mutation with slicing, extract the missing-prefix check.

- [ ] **Step 1: Replace the contents of `src/assertions/_classify.py`**

```python
import importlib
from types import ModuleType


def _resolve_dotted(
    target: str,
) -> tuple[ModuleType, list[str] | None]:
    parts = target.split('.')
    first_error: ModuleNotFoundError | None = None

    # Try each prefix from longest to shortest.
    for prefix_length in range(len(parts), 0, -1):
        head = '.'.join(parts[:prefix_length])
        tail_parts = parts[prefix_length:]
        try:
            module = importlib.import_module(head)
        except ModuleNotFoundError as exc:
            if not _is_missing_prefix_error(exc, head):
                # The prefix exists but raised inside its own
                # imports — propagate rather than mask as a bad
                # selector.
                raise
            if first_error is None:
                first_error = exc
            continue
        if not tail_parts:
            return module, None
        if len(tail_parts) > 2:
            raise LookupError(
                f'cannot resolve {target!r}: too many trailing '
                f'segments after module {head!r}'
            )
        return module, ['.'.join(tail_parts)]

    # No prefix imported. Re-raise the natural error.
    assert first_error is not None
    raise first_error


def _is_missing_prefix_error(
    exc: ModuleNotFoundError,
    head: str,
) -> bool:
    # The prefix itself is what's missing, vs an unrelated import
    # inside the prefix's module.
    return exc.name is not None and (
        exc.name == head or head.startswith(exc.name + '.')
    )
```

- [ ] **Step 2: Run the full test suite**

Run:
```bash
uv run python -m unittest discover -s tests -v 2>&1 | tail -10
```

Expected: every test passes (no test changes needed; coverage in `tests/test_targets.py::TestParseTarget` already exercises every path through `_resolve_dotted`).

- [ ] **Step 3: Run mypy**

Run:
```bash
uv run mypy
```

Expected: `Success: no issues found`.

- [ ] **Step 4: Commit**

```bash
git add src/assertions/_classify.py
git commit -m "Rewrite _resolve_dotted with range-based prefix loop"
```

---

## Task 2: Tighten `_dotted_name_for_path` return shape (a)

**Files:**
- Modify: `src/assertions/_loaders.py`
- Modify: `tests/test_loaders.py`

- [ ] **Step 1: Update `_dotted_name_for_path` and `_load_path_for_walk` in `src/assertions/_loaders.py`**

Replace the two functions:

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
```

`_exec_module_from_path` and `_load_path` are unchanged — included for context.

- [ ] **Step 2: Update `tests/test_loaders.py`**

Replace `TestDottedNameForPath`'s three test methods:

```python
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
            info = _dotted_name_for_path(target)
            self.assertIsNotNone(info)
            assert info is not None  # narrow for mypy
            dotted, rootdir = info
            self.assertEqual(dotted, 'pkg.sub.mod')
            self.assertEqual(rootdir, root)

    def test_returns_none_for_loose_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            target = root / 'loose.py'
            target.write_text('')
            self.assertIsNone(_dotted_name_for_path(target))

    def test_top_level_package_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            pkg = root / 'pkg'
            pkg.mkdir()
            (pkg / '__init__.py').write_text('')
            target = pkg / 'mod.py'
            target.write_text('')
            info = _dotted_name_for_path(target)
            self.assertIsNotNone(info)
            assert info is not None
            dotted, rootdir = info
            self.assertEqual(dotted, 'pkg.mod')
            self.assertEqual(rootdir, root)
```

(Note: `assert info is not None` after `assertIsNotNone` is a known
mypy idiom for type narrowing — `assertIsNotNone` doesn't narrow the
type for the type checker even though it raises at runtime.)

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
git add src/assertions/_loaders.py tests/test_loaders.py
git commit -m "Return tuple | None from _dotted_name_for_path"
```

---

## Task 3: Replace `_add_to_groups` with dict-based merge in `discover_targets` (d)

**Files:**
- Modify: `src/assertions/_targets.py`

- [ ] **Step 1: Replace the contents of `src/assertions/_targets.py`**

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
```

`_add_to_groups` is removed. The merge logic lives inside
`discover_targets` and uses a single dict pass instead of per-target
linear scans.

- [ ] **Step 2: Run the full test suite**

Run:
```bash
uv run python -m unittest discover -s tests -v 2>&1 | tail -10
```

Expected: every test passes (the `TestDiscoverTargets` tests for dedup,
module-then-selector, and merge-selectors observe behavior through
`discover_targets`'s return value, which is unchanged).

- [ ] **Step 3: Run mypy**

Run:
```bash
uv run mypy
```

Expected: `Success: no issues found`.

- [ ] **Step 4: Commit**

```bash
git add src/assertions/_targets.py
git commit -m "Merge target groups via dict[id(module)] in discover_targets"
```

---

## Task 4: Flatten `resolve_units` to a single iterator (e)

**Files:**
- Modify: `src/assertions/_resolve.py`
- Modify: `src/assertions/_runner.py`
- Modify: `tests/test_resolve.py`

- [ ] **Step 1: Update `src/assertions/_resolve.py`**

Replace the file's contents:

```python
import functools
import itertools
from contextlib import nullcontext
from types import ModuleType
from typing import Any, Callable, Iterator

from assertions._class_helpers import _public_methods
from assertions._discover import discover
from assertions._params import PARAMS_MARKER


def resolve_units(
    module: ModuleType,
    names: list[str] | None = None,
) -> Iterator[tuple[str, Callable[[], Any]]]:
    units = discover(module)
    if names is None:
        return itertools.chain.from_iterable(
            _expand_unit(unit, None) for unit in units
        )
    plan = _build_plan(units, names)
    return itertools.chain.from_iterable(
        _expand_unit(unit, plan[unit.__qualname__])
        for unit in units
        if unit.__qualname__ in plan
    )


def _expand_unit(
    unit: Any,
    method_filter: set[str] | None,
) -> Iterator[tuple[str, Callable[[], Any]]]:
    if isinstance(unit, type):
        instance = unit()
        cm = (
            instance
            if hasattr(instance, '__enter__')
            else nullcontext(instance)
        )
        with cm:
            for method_name in _public_methods(unit):
                if (
                    method_filter is not None
                    and method_name not in method_filter
                ):
                    continue
                bound = getattr(instance, method_name)
                yield from _expand_callable(bound, bound.__qualname__)
    else:
        yield from _expand_callable(unit, unit.__qualname__)


def _expand_callable(
    func: Callable[..., Any],
    qualname: str,
) -> Iterator[tuple[str, Callable[[], Any]]]:
    params = getattr(func, PARAMS_MARKER, None)
    if params is None:
        yield qualname, func
        return
    for i, args in enumerate(params):
        yield f'{qualname}[{i}]', functools.partial(func, *args)


def _build_plan(
    units: list[Any],
    names: list[str],
) -> dict[str, set[str] | None]:
    # plan[unit_qualname] = None  -> run as today (whole unit)
    #                    = set    -> run only these method names
    plan: dict[str, set[str] | None] = {}
    discovered_unit_names = {u.__qualname__: u for u in units}
    unmatched: list[str] = []
    for name in names:
        if '.' in name:
            head, _, method = name.partition('.')
            unit = discovered_unit_names.get(head)
            if (
                unit is None
                or not isinstance(unit, type)
                or method not in _public_methods(unit)
            ):
                unmatched.append(name)
                continue
            existing = plan.get(head, set())
            if existing is None:
                # already a whole-unit selector for this class — wins.
                continue
            existing.add(method)
            plan[head] = existing
        else:
            if name not in discovered_unit_names:
                unmatched.append(name)
                continue
            plan[name] = None  # whole unit; class form wins
    if unmatched:
        raise LookupError(f'no test units matched: {sorted(unmatched)}')
    return plan
```

Two notable behaviors:

- `_build_plan` runs synchronously inside `resolve_units` (before
  `chain.from_iterable` is constructed), so `LookupError` for
  unmatched selectors fires at `resolve_units(...)` call time — not
  at first iteration. The `test_validation_runs_before_any_iteration`
  test stays valid.
- `_expand_unit` is a generator with `with cm:` inside it. When
  `chain.from_iterable` advances from one unit's generator to the
  next, the previous generator is exhausted (running `__exit__`
  before the next `__enter__`). Lifecycle is sequential per class,
  not nested.

- [ ] **Step 2: Update `src/assertions/_runner.py` to use the flat iterator**

Replace the file's contents:

```python
from types import ModuleType

from assertions._resolve import resolve_units


def run(
    module: ModuleType,
    names: list[str] | None = None,
) -> list[tuple[str, Exception | None]]:
    results: list[tuple[str, Exception | None]] = []
    for name, call in resolve_units(module, names):
        try:
            call()
        except Exception as exc:
            results.append((name, exc))
        else:
            results.append((name, None))
    return results
```

One level of nesting removed.

- [ ] **Step 3: Update `tests/test_resolve.py`**

Replace the file's contents:

```python
import functools
import importlib
import unittest

from assertions._resolve import resolve_units


class TestResolveUnits(unittest.TestCase):
    def test_plain_function_yields_one_pair(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.all_pass',
        )
        pairs = list(resolve_units(mod))
        names = [name for name, _ in pairs]
        self.assertEqual(names, ['passes_one', 'passes_two'])
        # The first pair's callable is the function itself.
        self.assertIs(pairs[0][1], getattr(mod, 'passes_one'))

    def test_parameterized_function_yields_indexed_partials(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.params_simple',
        )
        pairs = list(resolve_units(mod))
        names = [name for name, _ in pairs]
        self.assertEqual(names, ['adds[0]', 'adds[1]'])
        for _, call in pairs:
            self.assertIsInstance(call, functools.partial)

    def test_class_with_context_manager_brackets_methods(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.class_calls_recorded',
        )
        mod.CALLS.clear()
        # Iterating the flat iterator runs __enter__ once before any
        # method call and __exit__ once after the last method.
        for _name, call in resolve_units(mod):
            call()
        self.assertEqual(
            mod.CALLS,
            ['enter', 'first', 'second', 'exit'],
        )

    def test_class_without_context_manager_runs_methods(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.class_simple',
        )
        names = [name for name, _ in resolve_units(mod)]
        self.assertEqual(names, ['Simple.first', 'Simple.second'])

    def test_class_method_selector_filters(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.class_simple',
        )
        names = [
            name
            for name, _ in resolve_units(mod, names=['Simple.first'])
        ]
        self.assertEqual(names, ['Simple.first'])

    def test_unmatched_name_raises_lookup_error(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.all_pass',
        )
        with self.assertRaises(LookupError) as ctx:
            resolve_units(mod, names=['nonexistent'])
        self.assertIn('nonexistent', str(ctx.exception))

    def test_validation_runs_before_any_iteration(self):
        # If any name is unmatched, the iterator is never advanced
        # because LookupError is raised at resolve_units(...) call
        # time, before chain.from_iterable is constructed.
        mod = importlib.import_module(
            'tests.fixtures.runner.class_calls_recorded',
        )
        mod.CALLS.clear()
        with self.assertRaises(LookupError):
            resolve_units(
                mod,
                names=['Recorded.first', 'Recorded.nonexistent'],
            )
        self.assertEqual(mod.CALLS, [])

    def test_class_form_wins_over_method_selector(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.class_simple',
        )
        names = [
            name
            for name, _ in resolve_units(
                mod,
                names=['Simple', 'Simple.first'],
            )
        ]
        # Both methods run, not just the one named in the selector.
        self.assertEqual(names, ['Simple.first', 'Simple.second'])

    def test_mixed_module_yields_pairs_in_order(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.class_mixed_with_function',
        )
        names = [name for name, _ in resolve_units(mod)]
        self.assertEqual(
            names,
            ['free_function', 'ClassUnit.method'],
        )

    def test_empty_module_returns_empty_iterator(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.empty',
        )
        self.assertEqual(list(resolve_units(mod)), [])

    def test_no_names_means_no_filtering(self):
        # When names is None, every discovered unit appears.
        mod = importlib.import_module(
            'tests.fixtures.runner.has_failure',
        )
        names = [name for name, _ in resolve_units(mod)]
        self.assertEqual(names, ['passes', 'fails'])


if __name__ == '__main__':
    unittest.main()
```

Notable changes in the rewritten tests:

- `test_mixed_module_yields_one_generator_per_unit` →
  `test_mixed_module_yields_pairs_in_order`. The "one generator per
  unit" semantic disappears with flattening.
- `test_empty_module_returns_empty_list` →
  `test_empty_module_returns_empty_iterator`. The return type is
  `Iterator`, not `list`, so the assertion materializes via `list(...)`.
- The `from contextlib import AbstractContextManager` import is
  removed (it wasn't actually used in the previous version either —
  ride-along cleanup).

- [ ] **Step 4: Run the full test suite**

Run:
```bash
uv run python -m unittest discover -s tests -v 2>&1 | tail -10
```

Expected: every test passes (current count 158).

- [ ] **Step 5: Run mypy**

Run:
```bash
uv run mypy
```

Expected: `Success: no issues found`.

- [ ] **Step 6: Commit**

```bash
git add src/assertions/_resolve.py src/assertions/_runner.py tests/test_resolve.py
git commit -m "Flatten resolve_units to a single iterator"
```

---

## Task 5: Smoke-test the cleanups

**Files:** none — verification only.

- [ ] **Step 1: existing CLI surface still works**

Run:
```bash
uv run python -m assertions tests/fixtures/runner/all_pass.py; echo "exit=$?"
uv run python -m assertions tests.fixtures.runner.class_simple.Simple.first; echo "exit=$?"
```

Expected: both exit 0.

- [ ] **Step 2: failure path still works**

Run:
```bash
uv run python -m assertions tests.fixtures.runner.has_failure; echo "exit=$?"
```

Expected: stdout contains `passes ... ok` and `fails ... FAIL: AssertionError:`; exit 1.

- [ ] **Step 3: parameterized expansion still works**

Run:
```bash
uv run python -m assertions tests.fixtures.runner.params_simple; echo "exit=$?"
```

Expected: stdout contains `adds[0] ... ok` and `adds[1] ... ok`; exit 0.

- [ ] **Step 4: class-level fixtures still bracket methods**

Run:
```bash
uv run python -m assertions tests.fixtures.runner.class_calls_recorded; echo "exit=$?"
```

Expected: per-method `... ok` lines; exit 0.

- [ ] **Step 5: unmatched selector still raises**

Run:
```bash
uv run python -m assertions tests.fixtures.runner.all_pass.nonexistent; echo "exit=$?"
```

Expected: non-zero exit; stderr contains `LookupError`.

- [ ] **Step 6: internal-import-error still propagates**

Run:
```bash
uv run python -m assertions tests.fixtures.runner.has_broken_import; echo "exit=$?"
```

Expected: non-zero exit; stderr contains `ModuleNotFoundError` whose
name is `this_dependency_does_not_exist`. (This verifies the
`_resolve_dotted` rewrite preserves the internal-vs-prefix-error
distinction.)

- [ ] **Step 7: confirm shape changes**

Run:
```bash
grep -c '_add_to_groups' src/assertions/*.py
```

Expected: `0` per file (the helper is removed).

Run:
```bash
grep -c 'list\[Iterator' src/assertions/_resolve.py
```

Expected: `0` (return type is now a single `Iterator`).

- [ ] **Step 8: No commit**

If any smoke step fails, return to the relevant earlier task and diagnose.

---

## Self-Review

- **Spec coverage:**
  - (b) `_resolve_dotted` rewritten with range-based loop and
    `_is_missing_prefix_error` helper — Task 1 ✓
  - (a) `_dotted_name_for_path` returns `tuple[str, Path] | None` —
    Task 2 ✓
  - (a) `_load_path_for_walk` adapts to the new return shape —
    Task 2 step 1 ✓
  - (a) tests in `tests/test_loaders.py` updated — Task 2 step 2 ✓
  - (d) `_add_to_groups` removed; `discover_targets` uses
    `dict[id(module), TargetGroup]` — Task 3 ✓
  - (e) `resolve_units` returns a single `Iterator` —
    Task 4 step 1 ✓
  - (e) `_runner.py` collapses to single for-loop —
    Task 4 step 2 ✓
  - (e) `tests/test_resolve.py` adapts to the new shape —
    Task 4 step 3 ✓
  - Eager validation preserved (LookupError before any iteration) —
    Task 4 step 1 (`_build_plan` runs above `chain.from_iterable`)
    + Task 4 step 3 test 7 ✓
  - Internal-import-error propagation preserved — Task 5 step 6 ✓
  - mypy clean — Tasks 1, 2, 3, 4 ✓
  - All previous tests pass — verified at every task's verification
    step ✓
- **Placeholder scan:** none.
- **Type consistency:**
  - `_resolve_dotted(target: str) -> tuple[ModuleType, list[str] |
    None]` unchanged across task boundaries.
  - `_dotted_name_for_path(path) -> tuple[str, Path] | None`
    consistent between definition (Task 2 step 1) and caller
    (`_load_path_for_walk`) and tests (Task 2 step 2).
  - `discover_targets` return type `list[TargetGroup]` unchanged.
  - `resolve_units(module, names=None) -> Iterator[tuple[str,
    Callable[[], Any]]]` matches between `_resolve.py` definition
    (Task 4 step 1) and `_runner.py` consumer (Task 4 step 2) and
    tests (Task 4 step 3).
  - `_build_plan(units, names: list[str])` (no `None` allowed) —
    consistent with the call site in `resolve_units` (which only
    invokes it when `names is not None`).
