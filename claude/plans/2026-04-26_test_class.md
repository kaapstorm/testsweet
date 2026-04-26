# `Test` Base Class Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Run Python via uv:** All Python invocations use `uv run python ...` (or `uv run mypy`). Never call `python` or `mypy` directly.
>
> **Code style:** ruff-format runs as a pre-commit hook with `quote-style = 'single'` and `line-length = 79`. Use single quotes in new files. If a commit is rejected because the hook reformatted files, re-stage and commit again.

**Goal:** Add `assertions.Test` so that subclassing it marks a class for discovery, its public methods become tests, and the class acts as a context manager for class-scoped fixtures. Update the runner and CLI to invoke `Test` subclasses end-to-end.

**Architecture:** `Test` uses `__init_subclass__` to set `TEST_MARKER = True` on every subclass — `discover()` is unchanged because classes are callable and inherit the marker. `_public_methods(cls)` walks the MRO leaf-first, collecting public methods in each class's `vars()` insertion order with leaf-priority on overrides. `run()` gains one branch: if a unit is a `Test` subclass, instantiate it, enter its context, run public methods (recording results as `(bound_method, exc_or_None)`), and exit the context. The CLI switches its display string from `__name__` to `__qualname__`.

**Tech Stack:** Python ≥3.11, `uv`, standard library only.

---

## File Structure

| Path | Action | Purpose |
|------|--------|---------|
| `src/assertions/_test_class.py` | create | `Test` base class + `_public_methods` helper |
| `src/assertions/_runner.py` | modify | Dispatch on `Test` subclass vs function |
| `src/assertions/__main__.py` | modify | Display via `__qualname__` |
| `src/assertions/__init__.py` | modify | Re-export `Test` |
| `tests/fixtures/runner/class_simple.py` | create | Two passing public methods |
| `tests/fixtures/runner/class_with_underscore_methods.py` | create | Underscore-named methods + one public |
| `tests/fixtures/runner/class_calls_recorded.py` | create | Records `__enter__`/`__exit__`/method calls |
| `tests/fixtures/runner/class_method_fails.py` | create | One pass, one assert-fail |
| `tests/fixtures/runner/class_enter_raises.py` | create | `__enter__` raises |
| `tests/fixtures/runner/class_exit_raises.py` | create | `__exit__` raises |
| `tests/fixtures/runner/class_with_inheritance.py` | create | Leaf + intermediate base + override |
| `tests/fixtures/runner/class_mixed_with_function.py` | create | One `@test` function + one `Test` subclass |
| `tests/test_test_class.py` | create | Tests for `Test` and `_public_methods` |
| `tests/test_runner.py` | modify | Add class-runner tests |
| `tests/test_cli.py` | modify | Add `__qualname__` display test |

---

## Task 1: Add `Test` test fixtures

**Files:**
- Create: `tests/fixtures/runner/class_simple.py`
- Create: `tests/fixtures/runner/class_with_underscore_methods.py`
- Create: `tests/fixtures/runner/class_calls_recorded.py`
- Create: `tests/fixtures/runner/class_method_fails.py`
- Create: `tests/fixtures/runner/class_enter_raises.py`
- Create: `tests/fixtures/runner/class_exit_raises.py`
- Create: `tests/fixtures/runner/class_with_inheritance.py`
- Create: `tests/fixtures/runner/class_mixed_with_function.py`

- [ ] **Step 1: Create `tests/fixtures/runner/class_simple.py`**

```python
from assertions import Test


class Simple(Test):
    def first(self):
        assert 1 + 1 == 2

    def second(self):
        assert 'a' + 'b' == 'ab'
```

- [ ] **Step 2: Create `tests/fixtures/runner/class_with_underscore_methods.py`**

```python
from assertions import Test


class WithUnderscores(Test):
    def _helper(self):
        raise AssertionError('helper should not run')

    def _data(self):
        raise AssertionError('data should not run')

    def public(self):
        assert True
```

- [ ] **Step 3: Create `tests/fixtures/runner/class_calls_recorded.py`**

```python
from assertions import Test


CALLS: list[str] = []


class Recorded(Test):
    def __enter__(self):
        CALLS.append('enter')

    def __exit__(self, exc_type, exc, tb):
        CALLS.append('exit')

    def first(self):
        CALLS.append('first')

    def second(self):
        CALLS.append('second')
```

- [ ] **Step 4: Create `tests/fixtures/runner/class_method_fails.py`**

```python
from assertions import Test


class HasFailure(Test):
    def passes(self):
        assert True

    def fails(self):
        assert 1 == 2
```

- [ ] **Step 5: Create `tests/fixtures/runner/class_enter_raises.py`**

```python
from assertions import Test


class EnterRaises(Test):
    def __enter__(self):
        raise RuntimeError('boom in enter')

    def never_runs(self):
        raise AssertionError('should not run')
```

- [ ] **Step 6: Create `tests/fixtures/runner/class_exit_raises.py`**

```python
from assertions import Test


class ExitRaises(Test):
    def __exit__(self, exc_type, exc, tb):
        raise RuntimeError('boom in exit')

    def passes(self):
        assert True
```

- [ ] **Step 7: Create `tests/fixtures/runner/class_with_inheritance.py`**

```python
from assertions import Test


class _Base(Test):
    def base_method(self):
        assert True

    def overridden(self):
        raise AssertionError('base override should not run')


class Leaf(_Base):
    def leaf_method(self):
        assert True

    def overridden(self):
        assert True
```

- [ ] **Step 8: Create `tests/fixtures/runner/class_mixed_with_function.py`**

```python
from assertions import Test, test


@test
def free_function():
    assert True


class ClassUnit(Test):
    def method(self):
        assert True
```

- [ ] **Step 9: Verify fixtures import cleanly (after Task 3 lands the `Test` symbol; for now just confirm no syntax errors)**

Run:
```bash
uv run python -c "
import ast, pathlib
for p in pathlib.Path('tests/fixtures/runner').glob('class_*.py'):
    ast.parse(p.read_text())
print('ok')
"
```

Expected: `ok`. (Full import will fail until `Test` is added in Task 3 — that's expected.)

- [ ] **Step 10: Commit**

```bash
git add tests/fixtures/runner/class_*.py
git commit -m "Add Test class test fixtures"
```

---

## Task 2: Write failing tests for `Test` and `_public_methods`

**Files:**
- Create: `tests/test_test_class.py`

- [ ] **Step 1: Create `tests/test_test_class.py`**

```python
import importlib
import unittest

from assertions import Test, discover
from assertions._markers import TEST_MARKER
from assertions._test_class import _public_methods


class TestMarkerPropagation(unittest.TestCase):
    def test_test_itself_has_no_marker(self):
        self.assertFalse(hasattr(Test, TEST_MARKER))

    def test_subclass_has_marker(self):
        class Sub(Test):
            pass

        self.assertIs(getattr(Sub, TEST_MARKER), True)

    def test_sub_subclass_has_marker(self):
        class Sub(Test):
            pass

        class SubSub(Sub):
            pass

        self.assertIs(getattr(SubSub, TEST_MARKER), True)


class TestDiscoverIntegration(unittest.TestCase):
    def test_discover_returns_test_subclass(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.class_simple',
        )
        result = discover(mod)
        self.assertEqual([cls.__name__ for cls in result], ['Simple'])

    def test_discover_skips_imported_test_base_itself(self):
        # Import Test into a namespace and confirm discover doesn't
        # return the Test class itself.
        import types

        mod = types.ModuleType('synthetic')
        mod.Test = Test  # type: ignore[attr-defined]
        result = discover(mod)
        self.assertEqual(result, [])


class TestPublicMethods(unittest.TestCase):
    def test_returns_leaf_methods_in_definition_order(self):
        class Cls(Test):
            def b_method(self):
                pass

            def a_method(self):
                pass

        names = [f.__name__ for f in _public_methods(Cls)]
        self.assertEqual(names, ['b_method', 'a_method'])

    def test_excludes_underscore_prefixed_methods(self):
        class Cls(Test):
            def _private(self):
                pass

            def public(self):
                pass

            def __dunder(self):
                pass

        names = [f.__name__ for f in _public_methods(Cls)]
        self.assertEqual(names, ['public'])

    def test_includes_inherited_methods_with_leaf_priority(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.class_with_inheritance',
        )
        names = [f.__name__ for f in _public_methods(mod.Leaf)]
        # Leaf-defined first in definition order, then base's
        # remaining methods. The override 'overridden' appears once,
        # in the leaf's position.
        self.assertEqual(
            names,
            ['leaf_method', 'overridden', 'base_method'],
        )


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run tests and confirm they fail on import**

Run:
```bash
uv run python -m unittest tests.test_test_class -v
```

Expected: failure on import — `ImportError: cannot import name 'Test' from 'assertions'`.

- [ ] **Step 3: Commit**

```bash
git add tests/test_test_class.py
git commit -m "Add failing tests for Test and _public_methods"
```

---

## Task 3: Implement `Test` and `_public_methods`

**Files:**
- Create: `src/assertions/_test_class.py`
- Modify: `src/assertions/__init__.py`

- [ ] **Step 1: Create `src/assertions/_test_class.py`**

```python
from typing import Callable

from assertions._markers import TEST_MARKER


class Test:
    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        setattr(cls, TEST_MARKER, True)

    def __enter__(self) -> 'Test':
        return self

    def __exit__(
        self,
        exc_type: object,
        exc: object,
        tb: object,
    ) -> None:
        return None


def _public_methods(cls: type) -> list[Callable]:
    seen: set[str] = set()
    out: list[Callable] = []
    for klass in cls.__mro__:
        if klass is object:
            continue
        for name, value in vars(klass).items():
            if name.startswith('_'):
                continue
            if not callable(value):
                continue
            if name in seen:
                continue
            seen.add(name)
            out.append(getattr(cls, name))
    return out
```

- [ ] **Step 2: Re-export `Test` from the package**

Replace the contents of `src/assertions/__init__.py` with:

```python
from assertions._discover import discover
from assertions._markers import test
from assertions._runner import run
from assertions._test_class import Test

__all__ = ['Test', 'discover', 'run', 'test']
```

- [ ] **Step 3: Run the new tests and confirm they pass**

Run:
```bash
uv run python -m unittest tests.test_test_class -v
```

Expected: all 8 tests pass.

- [ ] **Step 4: Run the full suite to confirm no regressions**

Run:
```bash
uv run python -m unittest discover -s tests -v
```

Expected: every existing test still passes; the new `tests.test_test_class` tests are included.

- [ ] **Step 5: Run mypy**

Run:
```bash
uv run mypy
```

Expected: `Success: no issues found`.

- [ ] **Step 6: Commit**

```bash
git add src/assertions/_test_class.py src/assertions/__init__.py
git commit -m "Add Test base class and _public_methods helper"
```

---

## Task 4: Write failing runner tests for `Test` classes

**Files:**
- Modify: `tests/test_runner.py`

- [ ] **Step 1: Append the following test class to `tests/test_runner.py` (before the `if __name__ == '__main__':` block at the end)**

```python
class TestRunClass(unittest.TestCase):
    def test_class_with_passing_methods(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.class_simple',
        )
        results = run(mod)
        self.assertEqual(len(results), 2)
        names = [bound.__qualname__ for bound, _ in results]
        self.assertEqual(names, ['Simple.first', 'Simple.second'])
        for _, exc in results:
            self.assertIsNone(exc)

    def test_underscore_methods_are_skipped(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.class_with_underscore_methods',
        )
        results = run(mod)
        names = [bound.__name__ for bound, _ in results]
        self.assertEqual(names, ['public'])

    def test_enter_and_exit_run_around_methods(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.class_calls_recorded',
        )
        mod.CALLS.clear()
        run(mod)
        self.assertEqual(
            mod.CALLS,
            ['enter', 'first', 'second', 'exit'],
        )

    def test_failing_method_does_not_abort_class(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.class_method_fails',
        )
        results = run(mod)
        self.assertEqual(len(results), 2)
        names = [bound.__name__ for bound, _ in results]
        self.assertEqual(names, ['passes', 'fails'])
        self.assertIsNone(results[0][1])
        self.assertIsInstance(results[1][1], AssertionError)

    def test_enter_exception_propagates(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.class_enter_raises',
        )
        with self.assertRaises(RuntimeError):
            run(mod)

    def test_exit_exception_propagates(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.class_exit_raises',
        )
        with self.assertRaises(RuntimeError):
            run(mod)

    def test_mixed_function_and_class_in_vars_order(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.class_mixed_with_function',
        )
        results = run(mod)
        names = [bound.__qualname__ for bound, _ in results]
        self.assertEqual(
            names,
            ['free_function', 'ClassUnit.method'],
        )
```

- [ ] **Step 2: Run the new tests and confirm they fail**

Run:
```bash
uv run python -m unittest tests.test_runner.TestRunClass -v
```

Expected: every test fails. The most likely failure mode is that `run()` calls the class constructor as if it were a test function (no special handling), so each class produces a single `(class, None)` or `(class, exc)` entry rather than per-method results.

- [ ] **Step 3: Commit**

```bash
git add tests/test_runner.py
git commit -m "Add failing runner tests for Test classes"
```

---

## Task 5: Extend `run` to dispatch on `Test` subclasses

**Files:**
- Modify: `src/assertions/_runner.py`

- [ ] **Step 1: Replace the contents of `src/assertions/_runner.py` with**

```python
from types import ModuleType
from typing import Callable

from assertions._discover import discover
from assertions._test_class import Test, _public_methods


def run(
    module: ModuleType,
) -> list[tuple[Callable, Exception | None]]:
    results: list[tuple[Callable, Exception | None]] = []
    for unit in discover(module):
        if isinstance(unit, type) and issubclass(unit, Test):
            instance = unit()
            with instance:
                for func in _public_methods(unit):
                    bound = getattr(instance, func.__name__)
                    try:
                        bound()
                    except Exception as exc:
                        results.append((bound, exc))
                    else:
                        results.append((bound, None))
        else:
            try:
                unit()
            except Exception as exc:
                results.append((unit, exc))
            else:
                results.append((unit, None))
    return results
```

- [ ] **Step 2: Run the runner tests and confirm they pass**

Run:
```bash
uv run python -m unittest tests.test_runner -v
```

Expected: all runner tests pass (existing 6 plus 7 new = 13).

- [ ] **Step 3: Run the full test suite**

Run:
```bash
uv run python -m unittest discover -s tests -v
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
git add src/assertions/_runner.py
git commit -m "Dispatch Test subclasses in run"
```

---

## Task 6: Switch CLI display to `__qualname__`

**Files:**
- Modify: `src/assertions/__main__.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Append a CLI test to `tests/test_cli.py` (before the `if __name__ == '__main__':` block)**

Add to the existing `class TestCli(unittest.TestCase):` body:

```python
    def test_class_method_qualname_in_output(self):
        result = _run_cli('tests.fixtures.runner.class_simple')
        self.assertEqual(result.returncode, 0)
        self.assertIn('Simple.first ... ok', result.stdout)
        self.assertIn('Simple.second ... ok', result.stdout)
```

- [ ] **Step 2: Run the new CLI test and confirm it fails**

Run:
```bash
uv run python -m unittest tests.test_cli.TestCli.test_class_method_qualname_in_output -v
```

Expected: FAIL — stdout contains `first ... ok` and `second ... ok` (from `__name__`) but not `Simple.first ... ok`.

- [ ] **Step 3: Replace the two `print` lines in `src/assertions/__main__.py`**

Replace `func.__name__` with `func.__qualname__` in both `print` calls. The full file should read:

```python
import importlib
import sys

from assertions._runner import run


USAGE = 'usage: python -m assertions <dotted.module>'


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print(USAGE, file=sys.stderr)
        return 2
    module = importlib.import_module(argv[0])
    results = run(module)
    failed = False
    for func, exc in results:
        if exc is None:
            print(f'{func.__qualname__} ... ok')
        else:
            print(
                f'{func.__qualname__} ... FAIL: '
                f'{type(exc).__name__}: {exc}'
            )
            failed = True
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
```

(If ruff-format collapses the split f-string, that's fine — re-stage and re-commit.)

- [ ] **Step 4: Run the CLI tests and confirm they pass**

Run:
```bash
uv run python -m unittest tests.test_cli -v
```

Expected: all CLI tests pass (existing 5 + 1 new = 6).

- [ ] **Step 5: Run the full suite**

Run:
```bash
uv run python -m unittest discover -s tests -v
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
git add src/assertions/__main__.py tests/test_cli.py
git commit -m "Display test results using __qualname__"
```

---

## Task 7: Smoke-test `examples/classes.py` end-to-end

**Files:** none — verification only.

- [ ] **Step 1: Run the example via the CLI**

Run:
```bash
uv run python -m assertions examples.classes; echo "exit=$?"
```

Expected output (order matches `vars()` insertion order in `examples/classes.py`):

```
OrThings.or_dicts ... ok
OrThings.uses_database ... ok
exit=0
```

- [ ] **Step 2: No commit**

If this fails, return to Task 5 or Task 6 and diagnose. Common causes:
- `examples/` may not be a package — check `examples/__init__.py` exists. If missing, that's a pre-existing issue, not a defect of this slice; report it as a concern.
- If output shows method names without the `OrThings.` prefix, the CLI changes from Task 6 didn't land.

---

## Self-Review

- **Spec coverage:**
  - `Test` does not have `TEST_MARKER` — Task 2 test 1 ✓
  - Subclass / sub-subclass have `TEST_MARKER` — Task 2 tests 2, 3 ✓
  - `__init_subclass__` sets the marker — Task 3 implementation ✓
  - `discover` returns `Test` subclasses unchanged — Task 2 test 4; relies on existing discover behavior ✓
  - `discover` does not return `Test` itself — Task 2 test 5 ✓
  - `_public_methods` leaf-defined definition order — Task 2 test 6 ✓
  - `_public_methods` excludes underscore-prefixed — Task 2 test 7 ✓
  - `_public_methods` MRO leaf-priority — Task 2 test 8 ✓
  - Class with passing methods returns bound methods with correct qualnames — Task 4 test 1 ✓
  - Underscore methods skipped at runtime — Task 4 test 2 ✓
  - `__enter__`/`__exit__` wrap methods together — Task 4 test 3 ✓
  - Failing method continues to next, exit still runs — Task 4 test 4; combined with test 3 fixture pattern, exit runs after a fail ✓
  - `__enter__` exception propagates — Task 4 test 5 ✓
  - `__exit__` exception propagates — Task 4 test 6 ✓
  - Mixed function + class results in `vars()` order — Task 4 test 7 ✓
  - CLI displays `ClassName.method` — Task 6 test 1 ✓
  - `examples/classes.py` runs end-to-end — Task 7 ✓
- **Placeholder scan:** none.
- **Type consistency:**
  - `Callable` used consistently in `_test_class.py` and `_runner.py`.
  - `_public_methods(cls: type) -> list[Callable]` matches usage in `_runner.py`.
  - The `(bound_method, exc_or_None)` shape matches what existing CLI tests expect after `__name__` → `__qualname__` switch.
  - `__init__.py` re-exports `Test` (added in Task 3) before `_runner.py` imports `_test_class` (Task 5) — no circular issue because `_runner.py` imports from `_test_class` directly.
