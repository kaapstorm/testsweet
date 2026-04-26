# `test_params` / `test_params_lazy` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Run Python via uv:** All Python invocations use `uv run python ...` (or `uv run mypy`). Never call `python` or `mypy` directly.
>
> **Code style:** ruff-format runs as a pre-commit hook (`quote-style = 'single'`, `line-length = 79`). Use single quotes in new files. If a commit is rejected because the hook reformatted files, re-stage and commit again.

**Goal:** Add eager (`@test_params`) and lazy (`@test_params_lazy`) parameterizing decorators, and refactor the runner so results are `(name: str, exc | None)` tuples and `_public_methods` returns `list[str]`.

**Architecture:** Both decorators store an iterable on the function under `PARAMS_MARKER`. `test_params` materializes to a tuple at decoration time (idempotent across runs); `test_params_lazy` stores it as-is (single-shot when fed a generator). The runner has one uniform invocation step that checks for `PARAMS_MARKER` and either calls the function once or iterates the stored value, generating names like `<qualname>[<i>]`. The runner produces all display names; the CLI just prints them.

**Tech Stack:** Python ≥3.11, `uv`, standard library only.

---

## File Structure

| Path | Action | Purpose |
|------|--------|---------|
| `src/assertions/_params.py` | create | `test_params`, `test_params_lazy`, `PARAMS_MARKER` |
| `src/assertions/_runner.py` | modify | `(name, exc)` results; uniform `_invoke` with param dispatch |
| `src/assertions/_test_class.py` | modify | `_public_methods` returns `list[str]` |
| `src/assertions/__main__.py` | modify | Drop `__qualname__` use |
| `src/assertions/__init__.py` | modify | Re-export `test_params`, `test_params_lazy` |
| `tests/test_test_class.py` | modify | Update existing `_public_methods` tests for new return type |
| `tests/test_runner.py` | modify | Update existing tests for new result shape; add param tests |
| `tests/test_cli.py` | modify | Add CLI test for parameterized output |
| `tests/test_params.py` | create | Decoration-time tests for both decorators |
| `tests/fixtures/runner/params_simple.py` | create | Eager: two passing tuples |
| `tests/fixtures/runner/params_with_failure.py` | create | Eager: middle tuple fails |
| `tests/fixtures/runner/params_empty.py` | create | Eager: `@test_params([])` |
| `tests/fixtures/runner/params_no_decoration.py` | create | Plain `@test` next to `@test_params` |
| `tests/fixtures/runner/params_generator.py` | create | Eager: generator argument |
| `tests/fixtures/runner/params_on_class_method.py` | create | Eager: on a `Test` method |
| `tests/fixtures/runner/params_lazy_generator.py` | create | Lazy: generator argument (single-shot) |
| `tests/fixtures/runner/params_lazy_list.py` | create | Lazy: list argument (re-iterable) |
| `tests/fixtures/runner/params_lazy_on_class_method.py` | create | Lazy: on a `Test` method |

---

## Task 1: Refactor `_public_methods` to return `list[str]`

**Files:**
- Modify: `src/assertions/_test_class.py`
- Modify: `src/assertions/_runner.py`
- Modify: `tests/test_test_class.py`

- [ ] **Step 1: Update existing `_public_methods` tests in `tests/test_test_class.py` to compare against `list[str]` directly**

Replace each existing assertion of the form `[f.__name__ for f in _public_methods(...)]` with `_public_methods(...)`. The updated test bodies are:

```python
class TestPublicMethods(unittest.TestCase):
    def test_returns_leaf_methods_in_definition_order(self):
        class Cls(Test):
            def b_method(self):
                pass

            def a_method(self):
                pass

        self.assertEqual(
            _public_methods(Cls),
            ['b_method', 'a_method'],
        )

    def test_excludes_underscore_prefixed_methods(self):
        class Cls(Test):
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
        # Leaf-defined first in definition order, then base's
        # remaining methods. The override 'overridden' appears once,
        # in the leaf's position.
        self.assertEqual(
            _public_methods(mod.Leaf),
            ['leaf_method', 'overridden', 'base_method'],
        )


class TestPublicMethodsCurrentBehavior(unittest.TestCase):
    # These tests document existing behavior of _public_methods for
    # cases that the spec did not explicitly call out. They are not
    # contracts — they are observations. Future changes to broaden or
    # narrow what counts as a "public method" should update them.

    def test_diamond_inheritance_follows_mro(self):
        class A(Test):
            def from_a(self):
                pass

            def shared(self):
                pass

        class B(Test):
            def from_b(self):
                pass

            def shared(self):
                pass

        class Leaf(A, B):
            def from_leaf(self):
                pass

        self.assertEqual(
            _public_methods(Leaf),
            ['from_leaf', 'from_a', 'shared', 'from_b'],
        )

    def test_staticmethod_is_included(self):
        class Cls(Test):
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
        class Cls(Test):
            @classmethod
            def a_class(cls):
                pass

            def regular(self):
                pass

        self.assertEqual(_public_methods(Cls), ['regular'])
```

- [ ] **Step 2: Run the updated tests; they must fail**

Run:
```bash
uv run python -m unittest tests.test_test_class -v
```

Expected: each `_public_methods` test fails because the function still returns `list[Callable]`, not `list[str]`. Marker propagation and discover-integration tests still pass.

- [ ] **Step 3: Update `_public_methods` in `src/assertions/_test_class.py`**

Replace the existing definition with:

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

- [ ] **Step 4: Update `_runner.py` to use the name directly**

Inside the `Test`-subclass branch of `run`, replace:

```python
for func in _public_methods(unit):
    bound = getattr(instance, func.__name__)
```

with:

```python
for name in _public_methods(unit):
    bound = getattr(instance, name)
```

(Leave the rest of the function unchanged for now — the result shape refactor happens in Task 2.)

- [ ] **Step 5: Run the test suite; everything passes**

Run:
```bash
uv run python -m unittest discover -s tests -v
```

Expected: all tests pass.

- [ ] **Step 6: Run mypy**

Run:
```bash
uv run mypy
```

Expected: `Success: no issues found`.

- [ ] **Step 7: Commit**

```bash
git add src/assertions/_test_class.py src/assertions/_runner.py tests/test_test_class.py
git commit -m "Return method names from _public_methods"
```

---

## Task 2: Refactor result shape to `(name, exc)` and update CLI

**Files:**
- Modify: `src/assertions/_runner.py`
- Modify: `src/assertions/__main__.py`
- Modify: `tests/test_runner.py`

- [ ] **Step 1: Update existing tests in `tests/test_runner.py` to read `(name, exc)`**

Replace the file contents (everything before `if __name__ == '__main__':`) with:

```python
import importlib
import unittest

from assertions import run


class TestRun(unittest.TestCase):
    def test_single_passing_test(self):
        mod = importlib.import_module('tests.fixtures.runner.all_pass')
        results = run(mod)
        self.assertEqual(len(results), 2)
        for _, exc in results:
            self.assertIsNone(exc)

    def test_single_failing_assert(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.has_failure',
        )
        results = run(mod)
        self.assertEqual(results[0][0], 'passes')
        self.assertIsNone(results[0][1])
        self.assertEqual(results[1][0], 'fails')
        self.assertIsInstance(results[1][1], AssertionError)

    def test_results_in_discover_order(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.has_failure',
        )
        results = run(mod)
        self.assertEqual(
            [name for name, _ in results],
            ['passes', 'fails'],
        )

    def test_empty_module_returns_empty_list(self):
        mod = importlib.import_module('tests.fixtures.runner.empty')
        results = run(mod)
        self.assertEqual(results, [])

    def test_non_assertion_exception_is_caught(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.non_assertion_error',
        )
        results = run(mod)
        self.assertEqual(len(results), 1)
        name, exc = results[0]
        self.assertEqual(name, 'raises_value_error')
        self.assertIsInstance(exc, ValueError)

    def test_keyboard_interrupt_propagates(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.keyboard_interrupt',
        )
        with self.assertRaises(KeyboardInterrupt):
            run(mod)


class TestRunClass(unittest.TestCase):
    def test_class_with_passing_methods(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.class_simple',
        )
        results = run(mod)
        self.assertEqual(len(results), 2)
        names = [name for name, _ in results]
        self.assertEqual(names, ['Simple.first', 'Simple.second'])
        for _, exc in results:
            self.assertIsNone(exc)

    def test_underscore_methods_are_skipped(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.class_with_underscore_methods',
        )
        results = run(mod)
        names = [name for name, _ in results]
        self.assertEqual(names, ['WithUnderscores.public'])

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
        names = [name for name, _ in results]
        self.assertEqual(
            names,
            ['HasFailure.passes', 'HasFailure.fails'],
        )
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
        names = [name for name, _ in results]
        self.assertEqual(
            names,
            ['free_function', 'ClassUnit.method'],
        )
```

(Keep the existing `if __name__ == '__main__':` trailer unchanged.)

- [ ] **Step 2: Run the updated tests; they must fail**

Run:
```bash
uv run python -m unittest tests.test_runner -v
```

Expected: most tests fail because the runner still returns `(callable, exc)` tuples, so e.g. `results[0][0]` is a function object rather than the string `'passes'`.

- [ ] **Step 3: Update `src/assertions/_runner.py` to produce `(name, exc)` results**

Replace the file contents with:

```python
from types import ModuleType
from typing import Callable

from assertions._discover import discover
from assertions._test_class import Test, _public_methods


def run(
    module: ModuleType,
) -> list[tuple[str, Exception | None]]:
    results: list[tuple[str, Exception | None]] = []
    for unit in discover(module):
        if isinstance(unit, type) and issubclass(unit, Test):
            instance = unit()
            with instance:
                for name in _public_methods(unit):
                    bound = getattr(instance, name)
                    _invoke(bound, bound.__qualname__, results)
        else:
            _invoke(unit, unit.__qualname__, results)
    return results


def _invoke(
    func: Callable,
    qualname: str,
    results: list[tuple[str, Exception | None]],
) -> None:
    try:
        func()
    except Exception as exc:
        results.append((qualname, exc))
    else:
        results.append((qualname, None))
```

- [ ] **Step 4: Update `src/assertions/__main__.py` to use `name` directly**

Replace the existing file with:

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
    for name, exc in results:
        if exc is None:
            print(f'{name} ... ok')
        else:
            print(f'{name} ... FAIL: {type(exc).__name__}: {exc}')
            failed = True
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
```

- [ ] **Step 5: Run the full test suite; everything passes**

Run:
```bash
uv run python -m unittest discover -s tests -v
```

Expected: all tests pass — runner tests, CLI tests, marker tests, discover tests, test_test_class tests.

- [ ] **Step 6: Run mypy**

Run:
```bash
uv run mypy
```

Expected: `Success: no issues found`.

- [ ] **Step 7: Commit**

```bash
git add src/assertions/_runner.py src/assertions/__main__.py tests/test_runner.py
git commit -m "Return (name, exc) tuples from run; drop __qualname__ in CLI"
```

---

## Task 3: Add `@test_params` and `@test_params_lazy` decorators

**Files:**
- Create: `src/assertions/_params.py`
- Modify: `src/assertions/__init__.py`
- Create: `tests/test_params.py`

- [ ] **Step 1: Create `tests/test_params.py` with failing decoration-time tests**

```python
import importlib
import unittest

from assertions import test_params, test_params_lazy
from assertions._markers import TEST_MARKER
from assertions._params import PARAMS_MARKER


class TestParamsEager(unittest.TestCase):
    def test_returns_same_function_object(self):
        def f(a, b):
            pass

        decorated = test_params([(1, 2)])(f)
        self.assertIs(decorated, f)

    def test_sets_test_marker(self):
        @test_params([(1,)])
        def f(a):
            pass

        self.assertIs(getattr(f, TEST_MARKER), True)

    def test_stores_params_as_tuple_matching_iterable(self):
        @test_params([(1, 2), (3, 4)])
        def f(a, b):
            pass

        self.assertEqual(
            getattr(f, PARAMS_MARKER),
            ((1, 2), (3, 4)),
        )

    def test_generator_is_eagerly_materialized(self):
        def gen():
            for i in range(3):
                yield (i,)

        @test_params(gen())
        def f(a):
            pass

        self.assertEqual(
            getattr(f, PARAMS_MARKER),
            ((0,), (1,), (2,)),
        )

    def test_decorated_function_still_callable(self):
        @test_params([(1, 2)])
        def f(a, b):
            return a + b

        self.assertEqual(f(1, 2), 3)


class TestParamsLazy(unittest.TestCase):
    def test_returns_same_function_object(self):
        def f(a, b):
            pass

        decorated = test_params_lazy([(1, 2)])(f)
        self.assertIs(decorated, f)

    def test_sets_test_marker(self):
        @test_params_lazy([(1,)])
        def f(a):
            pass

        self.assertIs(getattr(f, TEST_MARKER), True)

    def test_stores_iterable_by_identity(self):
        args = [(1, 2), (3, 4)]

        @test_params_lazy(args)
        def f(a, b):
            pass

        self.assertIs(getattr(f, PARAMS_MARKER), args)

    def test_generator_is_stored_unconsumed(self):
        def gen():
            for i in range(3):
                yield (i,)

        g = gen()

        @test_params_lazy(g)
        def f(a):
            pass

        self.assertIs(getattr(f, PARAMS_MARKER), g)

    def test_decorated_function_still_callable(self):
        @test_params_lazy([(1, 2)])
        def f(a, b):
            return a + b

        self.assertEqual(f(1, 2), 3)


class TestDiscoverIntegration(unittest.TestCase):
    def test_discover_returns_test_params_function(self):
        # Using the params_simple fixture (created in Task 4) — until
        # Task 4 lands, this test will fail at module-import time.
        mod = importlib.import_module(
            'tests.fixtures.runner.params_simple',
        )
        from assertions import discover

        result = discover(mod)
        names = [f.__name__ for f in result]
        self.assertIn('adds', names)


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run the new tests; they must fail on import**

Run:
```bash
uv run python -m unittest tests.test_params -v
```

Expected: `ImportError: cannot import name 'test_params' from 'assertions'`.

- [ ] **Step 3: Create `src/assertions/_params.py`**

```python
from typing import Callable, Iterable

from assertions._markers import TEST_MARKER


PARAMS_MARKER = '__assertions_params__'


def test_params(args_iterable: Iterable) -> Callable:
    materialized = tuple(args_iterable)

    def decorator(func: Callable) -> Callable:
        setattr(func, TEST_MARKER, True)
        setattr(func, PARAMS_MARKER, materialized)
        return func

    return decorator


def test_params_lazy(args_iterable: Iterable) -> Callable:
    def decorator(func: Callable) -> Callable:
        setattr(func, TEST_MARKER, True)
        setattr(func, PARAMS_MARKER, args_iterable)
        return func

    return decorator
```

- [ ] **Step 4: Update `src/assertions/__init__.py` to re-export the new decorators**

Replace the contents of `src/assertions/__init__.py` with:

```python
from assertions._discover import discover
from assertions._markers import test
from assertions._params import test_params, test_params_lazy
from assertions._runner import run
from assertions._test_class import Test

__all__ = [
    'Test',
    'discover',
    'run',
    'test',
    'test_params',
    'test_params_lazy',
]
```

- [ ] **Step 5: Run the new tests except `TestDiscoverIntegration` (the fixture lands in Task 4)**

Run:
```bash
uv run python -m unittest tests.test_params.TestParamsEager tests.test_params.TestParamsLazy -v
```

Expected: all 10 tests pass.

- [ ] **Step 6: Run the full suite; everything else still passes**

Run:
```bash
uv run python -m unittest discover -s tests -v 2>&1 | tail -10
```

Expected: previously-passing tests still pass; `TestDiscoverIntegration.test_discover_returns_test_params_function` fails because the `params_simple` fixture does not yet exist (`ModuleNotFoundError`). That failure is expected and will be fixed in Task 4.

- [ ] **Step 7: Run mypy**

Run:
```bash
uv run mypy
```

Expected: `Success: no issues found`.

- [ ] **Step 8: Commit**

```bash
git add src/assertions/_params.py src/assertions/__init__.py tests/test_params.py
git commit -m "Add test_params and test_params_lazy decorators"
```

---

## Task 4: Add params fixtures

**Files:**
- Create: `tests/fixtures/runner/params_simple.py`
- Create: `tests/fixtures/runner/params_with_failure.py`
- Create: `tests/fixtures/runner/params_empty.py`
- Create: `tests/fixtures/runner/params_no_decoration.py`
- Create: `tests/fixtures/runner/params_generator.py`
- Create: `tests/fixtures/runner/params_on_class_method.py`
- Create: `tests/fixtures/runner/params_lazy_generator.py`
- Create: `tests/fixtures/runner/params_lazy_list.py`
- Create: `tests/fixtures/runner/params_lazy_on_class_method.py`

- [ ] **Step 1: `params_simple.py`**

```python
from assertions import test_params


@test_params([(1, 1, 2), (2, 3, 5)])
def adds(a, b, expected):
    assert a + b == expected
```

- [ ] **Step 2: `params_with_failure.py`**

```python
from assertions import test_params


@test_params([(1, 1, 2), (1, 1, 99), (2, 3, 5)])
def adds(a, b, expected):
    assert a + b == expected
```

- [ ] **Step 3: `params_empty.py`**

```python
from assertions import test_params


@test_params([])
def never_runs(a):
    raise AssertionError('should not run')
```

- [ ] **Step 4: `params_no_decoration.py`**

```python
from assertions import test, test_params


@test
def plain():
    assert True


@test_params([(1, 1, 2)])
def parameterized(a, b, expected):
    assert a + b == expected
```

- [ ] **Step 5: `params_generator.py`**

```python
from assertions import test_params


def get_args():
    for i in range(3):
        yield (i, i + 1, 2 * i + 1)


@test_params(get_args())
def adds(a, b, expected):
    assert a + b == expected
```

- [ ] **Step 6: `params_on_class_method.py`**

```python
from assertions import Test, test_params


class Cls(Test):
    @test_params([(1, 2), (3, 4)])
    def method(self, a, b):
        assert a < b
```

- [ ] **Step 7: `params_lazy_generator.py`**

```python
from assertions import test_params_lazy


def get_args():
    for i in range(3):
        yield (i, i + 1, 2 * i + 1)


@test_params_lazy(get_args())
def adds(a, b, expected):
    assert a + b == expected
```

- [ ] **Step 8: `params_lazy_list.py`**

```python
from assertions import test_params_lazy


@test_params_lazy([(1, 1), (2, 2)])
def equals(a, b):
    assert a == b
```

- [ ] **Step 9: `params_lazy_on_class_method.py`**

```python
from assertions import Test, test_params_lazy


class Cls(Test):
    @test_params_lazy([(1, 2), (3, 4)])
    def method(self, a, b):
        assert a < b
```

- [ ] **Step 10: Verify fixtures import cleanly**

Run:
```bash
uv run python -c "
import importlib
for name in [
    'params_simple', 'params_with_failure', 'params_empty',
    'params_no_decoration', 'params_generator',
    'params_on_class_method', 'params_lazy_generator',
    'params_lazy_list', 'params_lazy_on_class_method',
]:
    importlib.import_module(f'tests.fixtures.runner.{name}')
print('ok')
"
```

Expected: `ok`.

- [ ] **Step 11: Confirm the previously-failing discover-integration test now passes**

Run:
```bash
uv run python -m unittest tests.test_params.TestDiscoverIntegration -v
```

Expected: `test_discover_returns_test_params_function` passes.

- [ ] **Step 12: Commit**

```bash
git add tests/fixtures/runner/params_*.py
git commit -m "Add test_params and test_params_lazy fixtures"
```

---

## Task 5: Add failing runner tests for params dispatch

**Files:**
- Modify: `tests/test_runner.py`

- [ ] **Step 1: Append a new test class to `tests/test_runner.py` (before the trailing `if __name__ == '__main__':`)**

```python
class TestRunParamsEager(unittest.TestCase):
    def test_runs_each_tuple_in_order(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.params_simple',
        )
        results = run(mod)
        names = [name for name, _ in results]
        self.assertEqual(names, ['adds[0]', 'adds[1]'])
        for _, exc in results:
            self.assertIsNone(exc)

    def test_failure_recorded_at_correct_index(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.params_with_failure',
        )
        results = run(mod)
        names = [name for name, _ in results]
        self.assertEqual(
            names,
            ['adds[0]', 'adds[1]', 'adds[2]'],
        )
        self.assertIsNone(results[0][1])
        self.assertIsInstance(results[1][1], AssertionError)
        self.assertIsNone(results[2][1])

    def test_empty_param_list_produces_no_results(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.params_empty',
        )
        self.assertEqual(run(mod), [])

    def test_function_without_params_unchanged(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.params_no_decoration',
        )
        results = run(mod)
        names = [name for name, _ in results]
        self.assertEqual(names, ['plain', 'parameterized[0]'])
        for _, exc in results:
            self.assertIsNone(exc)

    def test_accepts_generator(self):
        # The generator was consumed at decoration time, so the second
        # run() call sees the same materialized tuple.
        mod = importlib.import_module(
            'tests.fixtures.runner.params_generator',
        )
        first = run(mod)
        second = run(mod)
        self.assertEqual(
            [name for name, _ in first],
            ['adds[0]', 'adds[1]', 'adds[2]'],
        )
        self.assertEqual(
            [name for name, _ in second],
            ['adds[0]', 'adds[1]', 'adds[2]'],
        )

    def test_on_class_method(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.params_on_class_method',
        )
        results = run(mod)
        names = [name for name, _ in results]
        self.assertEqual(
            names,
            ['Cls.method[0]', 'Cls.method[1]'],
        )
        for _, exc in results:
            self.assertIsNone(exc)


class TestRunParamsLazy(unittest.TestCase):
    def test_runs_each_yielded_tuple(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.params_lazy_generator',
        )
        # Force a fresh import so the generator is freshly created
        # for this test (other tests in this class may also import
        # this fixture and consume the generator).
        importlib.reload(mod)
        results = run(mod)
        names = [name for name, _ in results]
        self.assertEqual(
            names,
            ['adds[0]', 'adds[1]', 'adds[2]'],
        )
        for _, exc in results:
            self.assertIsNone(exc)

    def test_generator_is_consumed_after_first_run(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.params_lazy_generator',
        )
        importlib.reload(mod)
        first = run(mod)
        second = run(mod)
        self.assertEqual(len(first), 3)
        self.assertEqual(second, [])

    def test_list_is_idempotent(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.params_lazy_list',
        )
        importlib.reload(mod)
        first = run(mod)
        second = run(mod)
        names_first = [name for name, _ in first]
        names_second = [name for name, _ in second]
        self.assertEqual(names_first, ['equals[0]', 'equals[1]'])
        self.assertEqual(names_second, ['equals[0]', 'equals[1]'])

    def test_on_class_method(self):
        mod = importlib.import_module(
            'tests.fixtures.runner.params_lazy_on_class_method',
        )
        importlib.reload(mod)
        results = run(mod)
        names = [name for name, _ in results]
        self.assertEqual(
            names,
            ['Cls.method[0]', 'Cls.method[1]'],
        )
        for _, exc in results:
            self.assertIsNone(exc)
```

- [ ] **Step 2: Run the new tests; they must fail**

Run:
```bash
uv run python -m unittest tests.test_runner.TestRunParamsEager tests.test_runner.TestRunParamsLazy -v
```

Expected: each test fails. The runner currently calls every discovered function with no args, so e.g. `adds()` raises `TypeError: adds() missing 3 required positional arguments`. The single result for each function will have name `'adds'` rather than `'adds[0]'`.

- [ ] **Step 3: Commit**

```bash
git add tests/test_runner.py
git commit -m "Add failing runner tests for test_params dispatch"
```

---

## Task 6: Wire param dispatch into `run`

**Files:**
- Modify: `src/assertions/_runner.py`

- [ ] **Step 1: Replace the contents of `src/assertions/_runner.py`**

```python
from types import ModuleType
from typing import Callable

from assertions._discover import discover
from assertions._params import PARAMS_MARKER
from assertions._test_class import Test, _public_methods


def run(
    module: ModuleType,
) -> list[tuple[str, Exception | None]]:
    results: list[tuple[str, Exception | None]] = []
    for unit in discover(module):
        if isinstance(unit, type) and issubclass(unit, Test):
            instance = unit()
            with instance:
                for name in _public_methods(unit):
                    bound = getattr(instance, name)
                    _invoke(bound, bound.__qualname__, results)
        else:
            _invoke(unit, unit.__qualname__, results)
    return results


def _invoke(
    func: Callable,
    qualname: str,
    results: list[tuple[str, Exception | None]],
) -> None:
    params = getattr(func, PARAMS_MARKER, None)
    if params is None:
        try:
            func()
        except Exception as exc:
            results.append((qualname, exc))
        else:
            results.append((qualname, None))
        return
    for i, args in enumerate(params):
        name = f'{qualname}[{i}]'
        try:
            func(*args)
        except Exception as exc:
            results.append((name, exc))
        else:
            results.append((name, None))
```

- [ ] **Step 2: Run the new param tests; they must pass**

Run:
```bash
uv run python -m unittest tests.test_runner.TestRunParamsEager tests.test_runner.TestRunParamsLazy -v
```

Expected: all 10 tests pass.

- [ ] **Step 3: Run the full suite**

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
git commit -m "Dispatch test_params via _invoke"
```

---

## Task 7: Add CLI test for parameterized output

**Files:**
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Append a method to the existing `class TestCli(unittest.TestCase):` body in `tests/test_cli.py`**

Add (before `if __name__ == '__main__':`):

```python
    def test_parameterized_indices_in_output(self):
        result = _run_cli('tests.fixtures.runner.params_simple')
        self.assertEqual(result.returncode, 0)
        self.assertIn('adds[0] ... ok', result.stdout)
        self.assertIn('adds[1] ... ok', result.stdout)
```

- [ ] **Step 2: Run the CLI tests**

Run:
```bash
uv run python -m unittest tests.test_cli -v
```

Expected: all 7 tests pass (existing 6 + 1 new).

- [ ] **Step 3: Commit**

```bash
git add tests/test_cli.py
git commit -m "Add CLI test for parameterized output"
```

---

## Task 8: Smoke-test `examples/functions.py`

**Files:** none — verification only.

- [ ] **Step 1: Run the example via the CLI**

Run:
```bash
uv run python -m assertions examples.functions; echo "exit=$?"
```

Expected output (order matches `vars()` insertion order in
`examples/functions.py`):

```
or_dicts ... ok
or_things[0] ... ok
or_things[1] ... ok
or_things[2] ... ok
uses_database ... ok
exit=0
```

- [ ] **Step 2: Run `examples/classes.py` to confirm class slice still works**

Run:
```bash
uv run python -m assertions examples.classes; echo "exit=$?"
```

Expected:

```
OrThings.or_dicts ... ok
OrThings.uses_database ... ok
exit=0
```

- [ ] **Step 3: No commit**

If either smoke test fails, return to the relevant earlier task and diagnose.

---

## Self-Review

- **Spec coverage:**
  - `@test_params` eager materializes iterable to tuple — Task 3, `_params.py` `test_params`; tests in Task 3 step 1 (`test_stores_params_as_tuple_matching_iterable`, `test_generator_is_eagerly_materialized`) ✓
  - `@test_params_lazy` stores iterable as-is — Task 3 implementation; tests `test_stores_iterable_by_identity`, `test_generator_is_stored_unconsumed` ✓
  - Both set `TEST_MARKER` — Task 3 implementation; tests `test_sets_test_marker` (×2) ✓
  - Decorated functions still callable directly — Task 3 tests (×2) ✓
  - Discover picks up params functions — Task 3 `TestDiscoverIntegration` (passes after Task 4) ✓
  - Runner unpacks each param tuple — Task 6 `_invoke`; tests in Task 5 `test_runs_each_tuple_in_order`, `test_runs_each_yielded_tuple` ✓
  - Result names of form `<qualname>[<i>]` — Task 6 implementation; multiple tests in Task 5 ✓
  - Failure at correct index — Task 5 `test_failure_recorded_at_correct_index` ✓
  - Empty params list produces no results — Task 5 `test_empty_param_list_produces_no_results` ✓
  - Plain functions unchanged — Task 5 `test_function_without_params_unchanged` ✓
  - Eager generator: idempotent across runs — Task 5 `test_accepts_generator` ✓
  - Lazy generator: single-shot — Task 5 `test_generator_is_consumed_after_first_run` ✓
  - Lazy list: idempotent — Task 5 `test_list_is_idempotent` ✓
  - Both decorators on class methods — Task 5 `TestRunParamsEager.test_on_class_method` and `TestRunParamsLazy.test_on_class_method` ✓
  - Result shape is `list[tuple[str, Exception | None]]` — Task 2 ✓
  - `_public_methods` returns `list[str]` — Task 1 ✓
  - CLI no longer references `__qualname__` — Task 2 ✓
  - CLI prints `<qualname>[<i>]` lines — Task 7 ✓
  - `examples/functions.py` end-to-end — Task 8 ✓
  - mypy clean — verified at the end of every implementation task ✓
- **Placeholder scan:** none.
- **Type consistency:**
  - `Iterable` and `Callable` used consistently in `_params.py`.
  - `_invoke` signature matches between Task 2 (initial form) and Task 6 (param-aware form).
  - Result shape `list[tuple[str, Exception | None]]` matches between `_runner.py`, the runner tests, and the CLI.
  - Fixture name `params_simple` referenced consistently in `tests/test_params.py`, `tests/test_runner.py`, and `tests/test_cli.py`.
  - `Cls.method[0]` qualname matches the fixture class names (`Cls.method`).
