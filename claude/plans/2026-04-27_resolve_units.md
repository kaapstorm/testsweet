# `resolve_units` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Run Python via uv:** All Python invocations use `uv run python ...` (or `uv run mypy`). Never call `python` or `mypy` directly.
>
> **Code style:** ruff-format runs as a pre-commit hook (`quote-style = 'single'`, `line-length = 79`). Use single quotes in new files. If a commit is rejected because the hook reformatted files, re-stage and commit again.

**Goal:** Move selector validation and unit-expansion logic out of `_runner.py` into a new `_resolve.py` module. The runner becomes a ~15-line iterate-call-catch loop. Behavior preserved.

**Architecture:** A new `resolve_units(module, names)` returns a list of generators. Each generator yields `(display_name, zero-arg-callable)` pairs and may use `with` internally for class-level fixtures. Validation is eager (raises `LookupError` before iteration starts); generators are lazy (no fixture entry until the runner iterates). The runner's job becomes: iterate generators, call each callable, catch `Exception`, append to results.

**Tech Stack:** Python ≥3.11, `uv`, standard library only (`functools.partial`, `contextlib.nullcontext`).

---

## File Structure

| Path | Action | Purpose |
|------|--------|---------|
| `src/assertions/_resolve.py` | create | `resolve_units`, `_expand_unit`, `_expand_callable`, `_build_plan` |
| `src/assertions/_runner.py` | rewrite | `run` only (~15 lines) |
| `tests/test_resolve.py` | create | Direct unit tests for `resolve_units` |

`tests/test_runner.py` is unchanged — its tests act as integration coverage for the new shape.

---

## Task 1: Create `_resolve.py` with all four functions

**Files:**
- Create: `src/assertions/_resolve.py`

This task adds the new module without modifying `_runner.py`. After this commit, `_resolve.py` exists alongside the unchanged `_runner.py` (which still has its own copies of `_build_plan`, `_run_unit`, `_invoke`). The runner is rewritten in Task 2; the duplication is removed atomically there.

- [ ] **Step 1: Create `src/assertions/_resolve.py`**

```python
import functools
from contextlib import nullcontext
from types import ModuleType
from typing import Any, Callable, Iterator

from assertions._class_helpers import _public_methods
from assertions._discover import discover
from assertions._params import PARAMS_MARKER


def resolve_units(
    module: ModuleType,
    names: list[str] | None = None,
) -> list[Iterator[tuple[str, Callable[[], Any]]]]:
    units = discover(module)
    plan = _build_plan(units, names)
    out: list[Iterator[tuple[str, Callable[[], Any]]]] = []
    for unit in units:
        if names is not None and unit.__qualname__ not in plan:
            continue
        method_filter = (
            plan.get(unit.__qualname__) if names is not None else None
        )
        out.append(_expand_unit(unit, method_filter))
    return out


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
    names: list[str] | None,
) -> dict[str, set[str] | None]:
    # plan[unit_qualname] = None  -> run as today (whole unit)
    #                    = set    -> run only these method names
    if names is None:
        return {}
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

Note: `_build_plan` here gains an `if names is None: return {}` guard so it can be called unconditionally from `resolve_units`. The original version (in `_runner.py`) was only called when `names is not None`; the new caller always calls it but the guard preserves the "no-op for `None`" semantics.

- [ ] **Step 2: Run the full test suite**

Run:
```bash
uv run python -m unittest discover -s tests -v 2>&1 | tail -10
```

Expected: every test passes. The new module exists but isn't imported by any other source file yet.

- [ ] **Step 3: Run mypy**

Run:
```bash
uv run mypy
```

Expected: `Success: no issues found`.

- [ ] **Step 4: Commit**

```bash
git add src/assertions/_resolve.py
git commit -m "Add _resolve.py with resolve_units and unit expansion"
```

---

## Task 2: Rewrite `_runner.py` to delegate to `resolve_units`

**Files:**
- Modify: `src/assertions/_runner.py`

- [ ] **Step 1: Replace the entire contents of `src/assertions/_runner.py`**

```python
from types import ModuleType

from assertions._resolve import resolve_units


def run(
    module: ModuleType,
    names: list[str] | None = None,
) -> list[tuple[str, Exception | None]]:
    results: list[tuple[str, Exception | None]] = []
    for unit_iter in resolve_units(module, names):
        for name, call in unit_iter:
            try:
                call()
            except Exception as exc:
                results.append((name, exc))
            else:
                results.append((name, None))
    return results
```

This deletes `_build_plan`, `_run_unit`, `_invoke`, and the imports of `nullcontext`, `Callable`, `discover`, `PARAMS_MARKER`, `_public_methods` from this file (they all live in `_resolve.py` now).

- [ ] **Step 2: Run the full test suite**

Run:
```bash
uv run python -m unittest discover -s tests -v 2>&1 | tail -10
```

Expected: every test passes. The runner tests (`tests/test_runner.py`) cover all the existing behaviors: function/class dispatch, parameterized expansion, selector validation, `LookupError` for unmatched names, `__enter__`/`__exit__` propagation. They run through `run()`, which now delegates to `resolve_units`.

- [ ] **Step 3: Run mypy**

Run:
```bash
uv run mypy
```

Expected: `Success: no issues found`.

- [ ] **Step 4: Confirm `_runner.py` shape**

Run:
```bash
wc -l src/assertions/_runner.py
```

Expected: ~15 lines.

Run:
```bash
grep -c "isinstance\|hasattr\|PARAMS_MARKER\|_public_methods\|_build_plan" src/assertions/_runner.py
```

Expected: `0`. The runner contains none of these terms.

- [ ] **Step 5: Commit**

```bash
git add src/assertions/_runner.py
git commit -m "Shrink _runner.py to a 15-line iterate-call-catch loop"
```

---

## Task 3: Add `tests/test_resolve.py`

**Files:**
- Create: `tests/test_resolve.py`

These are direct unit tests for `resolve_units`. Most existing scenarios are already covered through `test_runner.py`; the new tests document the new function's contract and pin generator semantics that aren't visible from the runner level.

- [ ] **Step 1: Create `tests/test_resolve.py`**

```python
import importlib
import unittest
from contextlib import AbstractContextManager

from assertions._resolve import resolve_units


class TestResolveUnits(unittest.TestCase):
    def test_plain_function_yields_one_pair(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.all_pass',
        )
        generators = resolve_units(mod)
        self.assertEqual(len(generators), 2)
        first_pairs = list(generators[0])
        self.assertEqual(len(first_pairs), 1)
        name, call = first_pairs[0]
        self.assertEqual(name, 'passes_one')
        self.assertIs(
            call,
            getattr(mod, 'passes_one'),
        )

    def test_parameterized_function_yields_indexed_partials(self):
        import functools

        mod = importlib.import_module(
            'tests.fixtures.runner.params_simple',
        )
        generators = resolve_units(mod)
        self.assertEqual(len(generators), 1)
        pairs = list(generators[0])
        names = [name for name, _ in pairs]
        self.assertEqual(names, ['adds[0]', 'adds[1]'])
        for _, call in pairs:
            self.assertIsInstance(call, functools.partial)

    def test_class_with_context_manager_brackets_methods(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.class_calls_recorded',
        )
        mod.CALLS.clear()
        generators = resolve_units(mod)
        self.assertEqual(len(generators), 1)
        # Consuming the generator should run __enter__ once before
        # any method, and __exit__ once after the last method.
        for _name, call in generators[0]:
            call()
        self.assertEqual(
            mod.CALLS,
            ['enter', 'first', 'second', 'exit'],
        )

    def test_class_without_context_manager_runs_methods(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.class_simple',
        )
        generators = resolve_units(mod)
        self.assertEqual(len(generators), 1)
        pairs = list(generators[0])
        names = [name for name, _ in pairs]
        self.assertEqual(names, ['Simple.first', 'Simple.second'])

    def test_class_method_selector_filters(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.class_simple',
        )
        generators = resolve_units(mod, names=['Simple.first'])
        self.assertEqual(len(generators), 1)
        pairs = list(generators[0])
        names = [name for name, _ in pairs]
        self.assertEqual(names, ['Simple.first'])

    def test_unmatched_name_raises_lookup_error(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.all_pass',
        )
        with self.assertRaises(LookupError) as ctx:
            resolve_units(mod, names=['nonexistent'])
        self.assertIn('nonexistent', str(ctx.exception))

    def test_validation_runs_before_any_iteration(self):
        # If any name is unmatched, no generator is created or
        # iterated. The class_calls_recorded fixture would record
        # 'enter' if its generator were started; verify CALLS stays
        # empty when LookupError fires.
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
        generators = resolve_units(
            mod,
            names=['Simple', 'Simple.first'],
        )
        pairs = list(generators[0])
        names = [name for name, _ in pairs]
        # Both methods run, not just the one named in the selector.
        self.assertEqual(names, ['Simple.first', 'Simple.second'])

    def test_mixed_module_yields_one_generator_per_unit(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.class_mixed_with_function',
        )
        generators = resolve_units(mod)
        self.assertEqual(len(generators), 2)
        all_names = []
        for gen in generators:
            for name, _ in gen:
                all_names.append(name)
        self.assertEqual(
            all_names,
            ['free_function', 'ClassUnit.method'],
        )

    def test_empty_module_returns_empty_list(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.empty',
        )
        self.assertEqual(resolve_units(mod), [])

    def test_no_names_means_no_filtering(self):
        # When names is None, every discovered unit appears.
        mod = importlib.import_module(
            'tests.fixtures.runner.has_failure',
        )
        generators = resolve_units(mod)
        all_names = []
        for gen in generators:
            for name, _ in gen:
                all_names.append(name)
        self.assertEqual(all_names, ['passes', 'fails'])


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run the new tests**

Run:
```bash
uv run python -m unittest tests.test_resolve -v
```

Expected: 11 tests pass.

- [ ] **Step 3: Run the full suite**

Run:
```bash
uv run python -m unittest discover -s tests -v 2>&1 | tail -10
```

Expected: every test passes; total ~156 (current 145 + 11 new).

- [ ] **Step 4: Run mypy**

Run:
```bash
uv run mypy
```

Expected: `Success: no issues found`.

- [ ] **Step 5: Commit**

```bash
git add tests/test_resolve.py
git commit -m "Add direct tests for resolve_units"
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

Expected: per-method `... ok` lines; exit 0. (The fixture itself records enter/method/exit calls into a module-level list; the runner's behavior is unchanged.)

- [ ] **Step 5: confirm runner shape**

Run:
```bash
wc -l src/assertions/_runner.py src/assertions/_resolve.py
```

Expected: `_runner.py` ~15 lines; `_resolve.py` ~80 lines.

- [ ] **Step 6: No commit**

If any smoke step fails, return to the relevant earlier task and diagnose.

---

## Self-Review

- **Spec coverage:**
  - `_resolve.py` created with `resolve_units`, `_expand_unit`, `_expand_callable`, `_build_plan` — Task 1 ✓
  - `_runner.py` rewritten to ~15 lines with no class/marker introspection — Task 2 ✓
  - `tests/test_runner.py` unchanged — preserved by Task 2 (no edits to that file) ✓
  - Generator-based protocol for context-managed iteration — Task 1 implementation ✓
  - Eager validation before any iteration — Task 3 test 7 ✓
  - Plain function yields one pair — Task 3 test 1 ✓
  - Parameterized function yields indexed partials — Task 3 test 2 ✓
  - Class with context manager brackets methods — Task 3 test 3 ✓
  - Class without context manager runs methods — Task 3 test 4 ✓
  - Selector filtering — Task 3 test 5 ✓
  - `LookupError` for unmatched names — Task 3 test 6 ✓
  - Class form wins over method selector — Task 3 test 8 ✓
  - Mixed module yields one generator per unit — Task 3 test 9 ✓
  - Empty module returns empty list — Task 3 test 10 ✓
  - `names=None` means no filtering — Task 3 test 11 ✓
  - mypy clean — Tasks 1, 2, 3 ✓
  - examples / CLI still work end-to-end — Task 4 ✓
- **Placeholder scan:** none.
- **Type consistency:**
  - `resolve_units(module, names=None) -> list[Iterator[...]]`
    consistent across Task 1 (definition) and Task 2 (caller).
  - `_expand_unit(unit, method_filter)` and
    `_expand_callable(func, qualname)` signatures match between
    definition and callers within `_resolve.py`.
  - `_build_plan(units, names)` accepts `names: list[str] | None`
    (note the `None` allowance — slight signature change vs the
    `_runner.py` original, where `names` was always non-None).
    The `if names is None: return {}` guard preserves callers.
  - `tests/test_resolve.py` imports
    `from assertions._resolve import resolve_units` consistently.
