# Drop `Test` Base Class Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the `Test` base class with class-level usage of the existing `@test` decorator, and have the runner duck-type the context-manager protocol so class fixtures are opt-in via `__enter__`/`__exit__` (typically by inheriting `contextlib.AbstractContextManager`).

**Architecture:** `@test` already sets `TEST_MARKER` on whatever it decorates. Allow it to mark classes too. The runner currently dispatches by `issubclass(unit, Test)`; switch to `isinstance(unit, type)` and use `contextlib.nullcontext(instance)` when the instance does not expose `__enter__`. `Test` and its module-level helpers move out, and all fixtures, tests, and docs migrate to the decorator style.

**Tech Stack:** Python 3.11+, stdlib only (`contextlib.nullcontext`, `contextlib.AbstractContextManager`), `unittest`, `uv`, `ruff`.

---

## File Structure

**Source files:**
- `src/assertions/_test_class.py` — keep `_public_methods`, remove `Test`. Rename file to `_class_helpers.py` (single-responsibility: helpers for class-shaped test units).
- `src/assertions/_runner.py` — drop the `Test` import; dispatch on `isinstance(unit, type)`; wrap entry in `nullcontext` when `__enter__` is absent.
- `src/assertions/__init__.py` — drop `Test` from imports and `__all__`.
- `src/assertions/_markers.py` — no change required (the existing `@test` already works on classes via `setattr`); add a docstring noting class usage.

**Test files:**
- `tests/test_test_class.py` — rename to `tests/test_class_helpers.py`. Drop `TestMarkerPropagation` (the `__init_subclass__` mechanism is gone). Replace `class Foo(Test):` with `@test class Foo:` throughout. Keep `_public_methods` tests. Add new tests covering `@test` on classes and the runner's duck-typing behavior.
- `tests/test_runner.py` — add tests for: (a) `@test` class without `__enter__` runs via `nullcontext`; (b) `@test` class inheriting `AbstractContextManager` runs `__enter__`/`__exit__`.
- `tests/fixtures/runner/class_*.py` — migrate every `class X(Test):` to `@test class X:` (and inherit `AbstractContextManager` where the fixture relies on enter/exit semantics: `class_enter_raises.py`, `class_exit_raises.py`, `class_calls_recorded.py`).

**Docs:**
- `doc/examples/classes.py` — already shows the target style; remove the old `class OrThings(Test):` example, keep the `@test` form. Add a no-fixture variant.
- `doc/roadmap/examples/django.py` — migrate to `@test class ThereIsASuperuser:` (or with `AbstractContextManager` if the example uses a fixture).
- `README.md` — update the "test class" example block under `Examples` to use `@test`.

**Plan deviations from the existing layout:** the rename `_test_class.py → _class_helpers.py` is justified because the file no longer hosts a class — only helpers. Skip the rename if the reviewer prefers to minimize churn; the rest of the plan is unaffected.

---

## Task 1: Add tests pinning down the new runner semantics (red)

**Files:**
- Create: `tests/fixtures/runner/class_decorated_simple.py`
- Create: `tests/fixtures/runner/class_decorated_with_cm.py`
- Modify: `tests/test_runner.py` (append two new test cases)

- [ ] **Step 1: Add a fixture for a decorated class with no context manager**

Create `tests/fixtures/runner/class_decorated_simple.py`:

```python
from assertions import test


@test
class Simple:
    def passes(self):
        assert True

    def fails(self):
        assert False
```

- [ ] **Step 2: Add a fixture for a decorated class that is a context manager**

Create `tests/fixtures/runner/class_decorated_with_cm.py`:

```python
from contextlib import AbstractContextManager

from assertions import test


calls: list[str] = []


@test
class WithCM(AbstractContextManager):
    def __enter__(self):
        calls.append('enter')
        self.value = 1
        return self

    def __exit__(self, exc_type, exc, tb):
        calls.append('exit')
        return None

    def uses_fixture(self):
        calls.append('test')
        assert self.value == 1
```

- [ ] **Step 3: Append runner tests for both fixtures**

Append to `tests/test_runner.py`:

```python
class TestDecoratedClass(unittest.TestCase):
    def test_runs_decorated_class_without_context_manager(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.class_decorated_simple',
        )
        results = run(mod)
        names = sorted(name for name, _ in results)
        self.assertEqual(names, ['Simple.fails', 'Simple.passes'])
        outcomes = {name: exc for name, exc in results}
        self.assertIsNone(outcomes['Simple.passes'])
        self.assertIsInstance(outcomes['Simple.fails'], AssertionError)

    def test_runs_decorated_class_with_context_manager(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.class_decorated_with_cm',
        )
        results = run(mod)
        self.assertEqual(
            [name for name, _ in results],
            ['WithCM.uses_fixture'],
        )
        self.assertIsNone(results[0][1])
        self.assertEqual(
            mod.calls,
            ['enter', 'test', 'exit'],
        )
```

If `import unittest`, `import importlib`, or `from assertions import run` is not already imported at the top of `tests/test_runner.py`, add them.

- [ ] **Step 4: Run the new tests and confirm they fail**

Run: `uv run python -m unittest tests.test_runner.TestDecoratedClass -v`
Expected: both tests fail. `test_runs_decorated_class_without_context_manager` fails because the runner currently treats a non-`Test` class as a callable and tries to call it (`TypeError` or empty results). `test_runs_decorated_class_with_context_manager` fails the same way.

- [ ] **Step 5: Commit**

```bash
git add tests/fixtures/runner/class_decorated_simple.py \
        tests/fixtures/runner/class_decorated_with_cm.py \
        tests/test_runner.py
git commit -m "test: pin down decorator-style class units (failing)"
```

---

## Task 2: Make the runner dispatch on `isinstance(unit, type)` and duck-type the cm protocol (green)

**Files:**
- Modify: `src/assertions/_runner.py`

- [ ] **Step 1: Update imports**

In `src/assertions/_runner.py`, replace:

```python
from assertions._test_class import Test, _public_methods
```

with:

```python
from contextlib import nullcontext

from assertions._test_class import _public_methods
```

(After Task 6 this import path becomes `assertions._class_helpers`; do not rename it yet — that change ships in Task 6.)

- [ ] **Step 2: Replace the `issubclass(unit, Test)` check in `_build_plan`**

In `src/assertions/_runner.py`, replace the block in `_build_plan` that currently reads:

```python
            if (
                unit is None
                or not (isinstance(unit, type) and issubclass(unit, Test))
                or method not in _public_methods(unit)
            ):
                unmatched.append(name)
                continue
```

with:

```python
            if (
                unit is None
                or not isinstance(unit, type)
                or method not in _public_methods(unit)
            ):
                unmatched.append(name)
                continue
```

- [ ] **Step 3: Replace the `issubclass(unit, Test)` check in `_run_unit` and add the duck-typed cm**

In `src/assertions/_runner.py`, replace `_run_unit` with:

```python
def _run_unit(
    unit,
    method_filter: set[str] | None,
    results: list[tuple[str, Exception | None]],
) -> None:
    if isinstance(unit, type):
        instance = unit()
        cm = instance if hasattr(instance, '__enter__') else nullcontext(instance)
        with cm:
            for name in _public_methods(unit):
                if method_filter is not None and name not in method_filter:
                    continue
                bound = getattr(instance, name)
                _invoke(bound, bound.__qualname__, results)
    else:
        _invoke(unit, unit.__qualname__, results)
```

- [ ] **Step 4: Run the new runner tests and confirm they pass**

Run: `uv run python -m unittest tests.test_runner.TestDecoratedClass -v`
Expected: both tests pass.

- [ ] **Step 5: Run the full test suite to confirm no regressions yet**

Run: `uv run python -m unittest discover -v`
Expected: pass. Existing `Test`-subclass fixtures still satisfy `isinstance(unit, type)` (they are still types and still carry `TEST_MARKER` via `__init_subclass__`), and they still expose `__enter__` from the `Test` base, so the new code path runs them unchanged.

- [ ] **Step 6: Commit**

```bash
git add src/assertions/_runner.py
git commit -m "feat(runner): dispatch class units by type, duck-type cm protocol"
```

---

## Task 3: Migrate runner fixtures from `Test` subclass to `@test`

**Files:**
- Modify: `tests/fixtures/runner/class_simple.py`
- Modify: `tests/fixtures/runner/class_method_fails.py`
- Modify: `tests/fixtures/runner/class_with_underscore_methods.py`
- Modify: `tests/fixtures/runner/class_with_inheritance.py`
- Modify: `tests/fixtures/runner/class_mixed_with_function.py`
- Modify: `tests/fixtures/runner/class_calls_recorded.py`
- Modify: `tests/fixtures/runner/class_enter_raises.py`
- Modify: `tests/fixtures/runner/class_exit_raises.py`
- Modify: `tests/fixtures/runner/params_on_class_method.py`
- Modify: `tests/fixtures/runner/params_lazy_on_class_method.py`

For each fixture, the migration rule is:
- If the original class only inherits `Test` and provides no `__enter__/__exit__`, replace `class X(Test):` with `@test\nclass X:` and drop the `Test` import in favor of `from assertions import test`.
- If the original class relies on enter/exit semantics, additionally inherit `contextlib.AbstractContextManager`.

- [ ] **Step 1: Migrate the no-fixture cases**

Apply the no-fixture rule to:

`tests/fixtures/runner/class_simple.py`:

```python
from assertions import test


@test
class Simple:
    def a_test(self):
        assert True

    def another_test(self):
        assert True
```

`tests/fixtures/runner/class_method_fails.py`:

```python
from assertions import test


@test
class HasFailure:
    def passes(self):
        assert True

    def fails(self):
        assert False
```

`tests/fixtures/runner/class_with_underscore_methods.py`:

```python
from assertions import test


@test
class WithUnderscores:
    def public(self):
        assert True

    def _private(self):
        raise NotImplementedError

    def __dunder(self):
        raise NotImplementedError
```

`tests/fixtures/runner/class_with_inheritance.py`:

```python
from assertions import test


class _Base:
    def base_method(self):
        assert True

    def overridden(self):
        raise AssertionError('base ran')


@test
class Leaf(_Base):
    def leaf_method(self):
        assert True

    def overridden(self):
        assert True
```

(Preserve the existing class bodies — only the marker mechanism changes. Read each existing file before editing to keep method bodies intact.)

`tests/fixtures/runner/class_mixed_with_function.py`:

```python
from assertions import test


@test
class ClassUnit:
    def class_method_test(self):
        assert True


@test
def function_test():
    assert True
```

`tests/fixtures/runner/params_on_class_method.py` and `tests/fixtures/runner/params_lazy_on_class_method.py`: replace `from assertions import Test, test_params[...]` with `from assertions import test, test_params[...]` and decorate the class with `@test`. Keep the `@test_params(...)` method-level decorators.

- [ ] **Step 2: Migrate the fixture-using cases**

`tests/fixtures/runner/class_enter_raises.py`:

```python
from contextlib import AbstractContextManager

from assertions import test


@test
class EnterRaises(AbstractContextManager):
    def __enter__(self):
        raise RuntimeError('enter failed')

    def __exit__(self, exc_type, exc, tb):
        return None

    def never_runs(self):
        raise AssertionError('should not run')
```

`tests/fixtures/runner/class_exit_raises.py`:

```python
from contextlib import AbstractContextManager

from assertions import test


@test
class ExitRaises(AbstractContextManager):
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        raise RuntimeError('exit failed')

    def runs_then_exit_raises(self):
        assert True
```

`tests/fixtures/runner/class_calls_recorded.py`:

```python
from contextlib import AbstractContextManager

from assertions import test


calls: list[str] = []


@test
class Recorded(AbstractContextManager):
    def __enter__(self):
        calls.append('enter')
        return self

    def __exit__(self, exc_type, exc, tb):
        calls.append('exit')
        return None

    def first(self):
        calls.append('first')

    def second(self):
        calls.append('second')
```

(If any of these fixtures previously stored module-level state under different names, preserve those names — read the file before rewriting.)

- [ ] **Step 3: Run the full suite**

Run: `uv run python -m unittest discover -v`
Expected: pass. The runner's new `isinstance(unit, type)` path picks up the decorator-marked classes; `_public_methods` is unchanged.

- [ ] **Step 4: Commit**

```bash
git add tests/fixtures/runner/class_*.py tests/fixtures/runner/params_*on_class_method.py
git commit -m "test: migrate runner fixtures to @test class style"
```

---

## Task 4: Update class-helper tests to the decorator style

**Files:**
- Modify: `tests/test_test_class.py`

- [ ] **Step 1: Read the existing file**

Read `tests/test_test_class.py` to confirm the current test bodies.

- [ ] **Step 2: Drop `TestMarkerPropagation`, switch to `@test`**

Replace the contents of `tests/test_test_class.py` with:

```python
import importlib
import unittest

from assertions import discover, test
from assertions._markers import TEST_MARKER
from assertions._test_class import _public_methods


class TestDecoratorOnClass(unittest.TestCase):
    def test_decorator_marks_class(self):
        @test
        class Cls:
            pass

        self.assertIs(getattr(Cls, TEST_MARKER), True)

    def test_undecorated_class_has_no_marker(self):
        class Cls:
            pass

        self.assertFalse(hasattr(Cls, TEST_MARKER))


class TestDiscoverIntegration(unittest.TestCase):
    def test_discover_returns_decorated_class(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.class_simple',
        )
        result = discover(mod)
        self.assertEqual([cls.__name__ for cls in result], ['Simple'])


class TestPublicMethods(unittest.TestCase):
    def test_returns_leaf_methods_in_definition_order(self):
        @test
        class Cls:
            def b_method(self):
                pass

            def a_method(self):
                pass

        self.assertEqual(
            _public_methods(Cls),
            ['b_method', 'a_method'],
        )

    def test_excludes_underscore_prefixed_methods(self):
        @test
        class Cls:
            def _private(self):
                pass

            def public(self):
                pass

            def __dunder(self):
                pass

        self.assertEqual(_public_methods(Cls), ['public'])

    def test_includes_inherited_methods_with_leaf_priority(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.class_with_inheritance',
        )
        self.assertEqual(
            _public_methods(mod.Leaf),
            ['leaf_method', 'overridden', 'base_method'],
        )


class TestPublicMethodsCurrentBehavior(unittest.TestCase):
    def test_diamond_inheritance_follows_mro(self):
        class A:
            def from_a(self):
                pass

            def shared(self):
                pass

        class B:
            def from_b(self):
                pass

            def shared(self):
                pass

        @test
        class Leaf(A, B):
            def from_leaf(self):
                pass

        self.assertEqual(
            _public_methods(Leaf),
            ['from_leaf', 'from_a', 'shared', 'from_b'],
        )

    def test_staticmethod_is_included(self):
        @test
        class Cls:
            @staticmethod
            def a_static():
                pass

            def regular(self):
                pass

        self.assertEqual(
            _public_methods(Cls),
            ['a_static', 'regular'],
        )

    def test_classmethod_is_excluded(self):
        @test
        class Cls:
            @classmethod
            def a_class(cls):
                pass

            def regular(self):
                pass

        self.assertEqual(_public_methods(Cls), ['regular'])


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 3: Run the file**

Run: `uv run python -m unittest tests.test_test_class -v`
Expected: pass.

- [ ] **Step 4: Commit**

```bash
git add tests/test_test_class.py
git commit -m "test: rework class-helper tests for decorator-style marking"
```

---

## Task 5: Remove `Test` from the public API and the source module

**Files:**
- Modify: `src/assertions/_test_class.py`
- Modify: `src/assertions/__init__.py`
- Modify: `src/assertions/_markers.py`

- [ ] **Step 1: Remove `Test` from `_test_class.py`**

Replace `src/assertions/_test_class.py` with:

```python
def _public_methods(cls: type) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
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
            out.append(name)
    return out
```

- [ ] **Step 2: Drop `Test` from `__init__.py`**

In `src/assertions/__init__.py`, remove the line `from assertions._test_class import Test` and the `'Test',` entry in `__all__`. Final file:

```python
from assertions._catches import catch_exceptions, catch_warnings
from assertions._config import ConfigurationError
from assertions._discover import discover
from assertions._markers import test
from assertions._params import test_params, test_params_lazy
from assertions._runner import run

__all__ = [
    'ConfigurationError',
    'catch_exceptions',
    'catch_warnings',
    'discover',
    'run',
    'test',
    'test_params',
    'test_params_lazy',
]
```

- [ ] **Step 3: Document class usage on `@test`**

In `src/assertions/_markers.py`, replace the body with:

```python
TEST_MARKER = '__assertions_test__'


def test(target):
    """Mark a function or class as a test unit.

    Applied to a function, the function is discovered and run as a
    standalone test. Applied to a class, the class is discovered and
    its public methods are run as tests; if the class implements the
    context-manager protocol (`__enter__`/`__exit__`, typically by
    inheriting `contextlib.AbstractContextManager`), the runner enters
    it for the duration of its method invocations.
    """
    setattr(target, TEST_MARKER, True)
    return target
```

- [ ] **Step 4: Run the full suite**

Run: `uv run python -m unittest discover -v`
Expected: pass. No remaining import of `Test` from `assertions` is reached because Tasks 3 and 4 already migrated every consumer.

- [ ] **Step 5: Search for stragglers**

Run: `uv run python -c "import assertions; assert not hasattr(assertions, 'Test')"`
Expected: exits cleanly.

Run: `grep -rn "from assertions import.*Test\b\|assertions._test_class import Test\|issubclass(.*Test)" src tests doc`
Expected: no output.

- [ ] **Step 6: Commit**

```bash
git add src/assertions/_test_class.py src/assertions/__init__.py src/assertions/_markers.py
git commit -m "refactor: remove Test base class; @test marks classes too"
```

---

## Task 6: Rename `_test_class.py` to `_class_helpers.py`

**Files:**
- Rename: `src/assertions/_test_class.py` → `src/assertions/_class_helpers.py`
- Rename: `tests/test_test_class.py` → `tests/test_class_helpers.py`
- Modify: `src/assertions/_runner.py`
- Modify: `tests/test_class_helpers.py` (after rename)

- [ ] **Step 1: Rename the source file using git**

Run: `git mv src/assertions/_test_class.py src/assertions/_class_helpers.py`

- [ ] **Step 2: Update the import in the runner**

In `src/assertions/_runner.py`, replace:

```python
from assertions._test_class import _public_methods
```

with:

```python
from assertions._class_helpers import _public_methods
```

- [ ] **Step 3: Rename the test file using git**

Run: `git mv tests/test_test_class.py tests/test_class_helpers.py`

- [ ] **Step 4: Update the test file's internal import**

In `tests/test_class_helpers.py`, replace:

```python
from assertions._test_class import _public_methods
```

with:

```python
from assertions._class_helpers import _public_methods
```

- [ ] **Step 5: Run the full suite**

Run: `uv run python -m unittest discover -v`
Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "refactor: rename _test_class to _class_helpers"
```

---

## Task 7: Update docs and examples

**Files:**
- Modify: `doc/examples/classes.py`
- Modify: `doc/roadmap/examples/django.py`
- Modify: `README.md`

- [ ] **Step 1: Replace `doc/examples/classes.py` with the decorator style**

Read the file first, then replace its contents with:

```python
from contextlib import AbstractContextManager

from assertions import test


# Plain class: @test marks it; all public methods are tests.
@test
class OrThings:
    def __init__(self):
        self.dict1 = {'foo': 1}
        self.dict2 = {'bar': 2}

    def or_dicts(self):
        assert self.dict1 | self.dict2 == {'foo': 1, 'bar': 2}

    def _not_a_test(self):
        raise NotImplementedError


# Class fixture: implement the context-manager protocol. Inheriting
# AbstractContextManager is idiomatic but not required — the runner
# duck-types __enter__/__exit__.
@test
class UsesDatabase(AbstractContextManager):
    def __init__(self):
        self.db = {}

    def __enter__(self):
        self.db = {'foo': 1}
        return self

    def __exit__(self, exc_type, exc, tb):
        self.db.clear()
        return None

    def has_foo(self):
        assert 'foo' in self.db
```

- [ ] **Step 2: Update `doc/roadmap/examples/django.py`**

Replace the contents of `doc/roadmap/examples/django.py` with:

```python
from assertions import test
from assertions.django import uses_db


# assertions.django.uses_db decorates functions and classes
@uses_db
@test
def there_is_a_superuser():
    assert User.objects.filter(is_superuser=True).exists()


@uses_db
@test
class ThereIsASuperuser:
    def there_is_a_superuser(self):
        assert User.objects.filter(is_superuser=True).exists()
```

(The current file does not provide `__enter__`/`__exit__`, so no `AbstractContextManager` inheritance is needed.)

- [ ] **Step 3: Update the test-class block in `README.md`**

In `README.md`, replace the existing block:

```python
from assertions import Test

class OrThings(Test):
    def or_dicts(self):
        assert {'foo': 1} | {'bar': 2} == {'foo': 1, 'bar': 2}
```

with:

```python
from assertions import test


@test
class OrThings:
    def or_dicts(self):
        assert {'foo': 1} | {'bar': 2} == {'foo': 1, 'bar': 2}
```

- [ ] **Step 4: Sanity-check the example file imports**

Run: `uv run python -c "import importlib.util, pathlib; spec = importlib.util.spec_from_file_location('classes', pathlib.Path('doc/examples/classes.py')); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)"`
Expected: exits cleanly (no `ImportError`, no `NameError`).

- [ ] **Step 5: Run the full suite once more**

Run: `uv run python -m unittest discover -v`
Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add doc/examples/classes.py doc/roadmap/examples/django.py README.md
git commit -m "docs: drop Test base class from examples and README"
```

---

## Task 8: Final verification

- [ ] **Step 1: Confirm `Test` is fully gone from the codebase**

Run: `grep -rn "\bTest\b" src tests doc | grep -v "TestMarker\|unittest\|TestCase\|Tests\b" || true`
Expected: only matches relating to `unittest.TestCase` or `Tests` words inside class names like `TestRunner`. No `assertions.Test` references.

- [ ] **Step 2: Run the full test suite via the project entrypoint**

Run: `uv run python -m unittest discover -v`
Expected: pass.

- [ ] **Step 3: Run the project's own self-discovery**

Run: `uv run python -m assertions tests`
Expected: pass (any pre-existing failures unrelated to this change are still pre-existing; flag them rather than masking).

- [ ] **Step 4: Format the changed Python files**

Run: `uv run pre-commit run --all-files`
Expected: pass, or pass after a single auto-format pass.

- [ ] **Step 5: Final commit if formatting changed anything**

```bash
git status --short
# If anything is dirty:
git add -A
git commit -m "style: ruff-format after Test removal"
```
