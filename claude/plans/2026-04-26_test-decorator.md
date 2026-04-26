# `@test` Decorator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Run Python via uv:** All Python invocations use `uv run python ...`. The `assertions` package is `pip install`ed (editable) with `uv pip install -e .` so imports resolve.

**Goal:** Implement the `@test` marker decorator so that the first example in `README.md` imports and runs.

**Architecture:** A single decorator that sets a sentinel attribute (`__assertions_test__ = True`) on the decorated function and returns it unchanged. The marker name lives in a shared module-level constant (`TEST_MARKER`) so future discovery code reads from the same source the decorator writes to. No registry, no wrapping, no assert introspection.

**Tech Stack:** Python ≥3.11, `uv` for environment management, standard-library `unittest` for tests (the `assertions` runner does not yet exist).

---

## File Structure

| Path | Action | Purpose |
|------|--------|---------|
| `src/assertions/__init__.py` | create | Public API: re-exports `test` |
| `src/assertions/_markers.py` | create | Defines `TEST_MARKER` and the `test` decorator |
| `tests/__init__.py` | create | Marks `tests/` as a package for `unittest` discovery |
| `tests/test_markers.py` | create | Unit tests for the decorator |

---

## Task 1: Set up the package and dev environment

**Files:**
- Create: `src/assertions/__init__.py` (empty placeholder for now)
- Create: `tests/__init__.py` (empty)

- [ ] **Step 1: Create the empty package files**

```bash
mkdir -p src/assertions tests
: > src/assertions/__init__.py
: > tests/__init__.py
```

- [ ] **Step 2: Install the package in editable mode into the uv venv**

Run:
```bash
uv pip install -e .
```

Expected: completes successfully, installs `Assertions` in editable mode.

- [ ] **Step 3: Verify the package imports**

Run:
```bash
uv run python -c "import assertions; print('ok')"
```

Expected output: `ok`

- [ ] **Step 4: Commit**

```bash
git add src/assertions/__init__.py tests/__init__.py
git commit -m "Scaffold assertions package and tests directory"
```

---

## Task 2: Write failing tests for the `test` decorator

**Files:**
- Create: `tests/test_markers.py`

- [ ] **Step 1: Write the test module**

Create `tests/test_markers.py` with:

```python
import unittest

from assertions import test
from assertions._markers import TEST_MARKER


class TestDecorator(unittest.TestCase):

    def test_returns_same_function_object(self):
        def f():
            pass
        self.assertIs(test(f), f)

    def test_sets_marker_attribute_to_true(self):
        @test
        def f():
            pass
        self.assertTrue(getattr(f, TEST_MARKER))

    def test_decorated_function_still_runs_and_returns_value(self):
        @test
        def f():
            return 42
        self.assertEqual(f(), 42)

    def test_undecorated_function_has_no_marker(self):
        def f():
            pass
        self.assertFalse(hasattr(f, TEST_MARKER))

    def test_marker_name_constant(self):
        self.assertEqual(TEST_MARKER, "__assertions_test__")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to confirm they fail**

Run:
```bash
uv run python -m unittest tests.test_markers -v
```

Expected: failure on import — `ImportError: cannot import name 'test' from 'assertions'` (or equivalent on `_markers`).

- [ ] **Step 3: Commit**

```bash
git add tests/test_markers.py
git commit -m "Add failing tests for @test decorator"
```

---

## Task 3: Implement the `test` decorator

**Files:**
- Create: `src/assertions/_markers.py`
- Modify: `src/assertions/__init__.py`

- [ ] **Step 1: Implement the marker module**

Create `src/assertions/_markers.py` with:

```python
TEST_MARKER = "__assertions_test__"


def test(func):
    setattr(func, TEST_MARKER, True)
    return func
```

- [ ] **Step 2: Re-export `test` from the package**

Replace the contents of `src/assertions/__init__.py` with:

```python
from assertions._markers import test

__all__ = ["test"]
```

- [ ] **Step 3: Run the tests to confirm they pass**

Run:
```bash
uv run python -m unittest tests.test_markers -v
```

Expected: all 5 tests pass.

- [ ] **Step 4: Commit**

```bash
git add src/assertions/_markers.py src/assertions/__init__.py
git commit -m "Add @test marker decorator"
```

---

## Task 4: Verify the README example runs end-to-end

**Files:**
- (no source changes — sanity check only)

- [ ] **Step 1: Run the README example as a one-liner**

Run:
```bash
uv run python -c "
from assertions import test

@test
def or_dicts():
    assert {'foo': 1} | {'bar': 2} == {'foo': 1, 'bar': 2}

or_dicts()
assert or_dicts.__assertions_test__ is True
print('ok')
"
```

Expected output: `ok`

- [ ] **Step 2: No commit needed**

This is a verification step. If it fails, return to Task 3 and diagnose.

---

## Self-Review

- **Spec coverage:**
  - Module layout (`__init__.py`, `_markers.py`) — Task 3 ✓
  - Decorator returns same function — test 1 ✓
  - Sets `__assertions_test__ = True` — test 2 ✓
  - Decorated function still callable with normal return — test 3 ✓
  - Undecorated functions have no marker — test 4 ✓
  - `TEST_MARKER` constant accessible and matches — test 5 ✓
  - README example imports and runs — Task 4 ✓
  - Out-of-scope items (discovery, runner, `Test`, introspection) — correctly absent
- **Placeholder scan:** none.
- **Type consistency:** `TEST_MARKER`, `test`, `__assertions_test__` referenced consistently across tasks.
