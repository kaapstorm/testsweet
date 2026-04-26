# Design: `Test` base class

## Scope

Add a `Test` base class so that a subclass is itself a test unit:

- The class is marked for discovery.
- All public methods on the class (and on its non-`Test`, non-`object`
  bases) are tests.
- The class is a context manager whose `__enter__` / `__exit__` runs
  once around the methods, providing class-scoped fixtures.

Out of scope for this slice:

- File-path / package-walk discovery
- Bare `python -m assertions` auto-discovery
- Test selectors (`tests.foo:bar`)
- `test_params`
- `assert_raises` / `assert_warns`
- Per-method context manager wrapping (the class manager wraps all
  methods together)
- Distinguishing fixture errors from test failures in the result list
- Capturing or formatting tracebacks

## Approach

A `Test` base class uses `__init_subclass__` to set `TEST_MARKER = True`
on every subclass automatically. `Test` itself does not carry the
marker, so importing `Test` into a test module does not pollute
discovery.

`discover()` is unchanged: classes are callable and inherit the marker
from their (non-`Test`) decorated ancestor, so the existing
`callable(value) and getattr(value, TEST_MARKER, False) is True` filter
already returns `Test` subclasses.

`run()` grows a single dispatch: if a unit is a class that is a subclass
of `Test`, run it the class way; otherwise treat it as a function.

The CLI switches its display string from `func.__name__` to
`func.__qualname__`. Free functions are unchanged (`__qualname__ ==
__name__`); bound methods print as `ClassName.method_name`.

## Public surface

```python
from assertions import Test


class MyTests(Test):
    def __init__(self):
        self.value = 0

    def __enter__(self):
        self.value = 1

    def __exit__(self, exc_type, exc, tb):
        self.value = 0

    def my_test(self):
        assert self.value == 1
```

The contract:

- A class extending `Test` is automatically marked as a test unit.
- `__init__`, `__enter__`, `__exit__` are optional. If omitted, the
  class behaves like an empty context manager.
- A method is a test iff it is callable and its name does not start
  with an underscore.

## Behavior

### `Test` and the marker

```python
class Test:
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        setattr(cls, TEST_MARKER, True)
```

- `Test` does not carry `TEST_MARKER`.
- Every subclass of `Test`, transitive or direct, carries
  `TEST_MARKER == True` as a class attribute.

### Method discovery: leaf-first MRO walk

A helper iterates `cls.__mro__`, skipping `object`, and yields each
class's `vars()` items in insertion order, deduplicating by name with
leaf-priority:

```python
def _public_methods(cls):
    seen = set()
    out = []
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

Properties:

- The leaf's own methods appear first, in definition order.
- Each ancestor (above `Test`) contributes its remaining methods in
  definition order.
- Methods overridden by the leaf appear once, in the leaf's slot.
- `Test` and `object` contribute nothing (they have no public methods).
- Returns unbound function objects (i.e., values from `getattr(cls,
  name)`); the runner binds them to an instance.

### `run` dispatch

For each unit returned by `discover(module)`, in order:

```python
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
    # existing function path: call unit(); record (unit, exc_or_None).
```

- The class is instantiated exactly once per `run` call.
- `__enter__` runs once before the methods; `__exit__` runs once after,
  including when a method raises (the existing `try/except` is around
  the method call, so `with` sees no exception and `__exit__` is called
  with `(None, None, None)`).
- An exception raised by `__enter__` or `__exit__` is **not** caught;
  it propagates out of `run` and aborts the rest of the run. This
  matches the existing rule that `BaseException` propagates — fixture
  failures are not tracked alongside test results in this slice.
- For each method, the result tuple records the bound method (so
  `result[0].__qualname__` gives `ClassName.method_name`).

### CLI display

`src/assertions/__main__.py` uses `func.__qualname__` instead of
`func.__name__` when formatting each result line:

```
<func.__qualname__> ... ok
<func.__qualname__> ... FAIL: <type-name>: <exc>
```

Free-function output is unchanged (`__qualname__` equals `__name__`
for top-level functions). Bound methods print as
`ClassName.method_name`.

The exit-code rule is unchanged.

## Module layout

| File | Action | Purpose |
|------|--------|---------|
| `src/assertions/_test_class.py` | create | Defines `Test`; defines `_public_methods` |
| `src/assertions/_runner.py` | modify | Dispatch on `Test` vs function |
| `src/assertions/__main__.py` | modify | Use `__qualname__` for display |
| `src/assertions/__init__.py` | modify | Re-export `Test` |

`_test_class.py` is its own module because it owns a distinct
responsibility (the class shape + the method-collection rule).
`_public_methods` lives there rather than in `_runner.py` because it is
a property of how a `Test` class exposes its tests, not how the runner
invokes them.

## Tests

### `tests/test_test_class.py`

1. `Test` itself does not have `TEST_MARKER`.
2. A subclass of `Test` has `TEST_MARKER == True`.
3. A subclass of a subclass of `Test` also has `TEST_MARKER == True`.
4. `discover` returns a `Test` subclass present in a module.
5. `discover` does not return `Test` itself when imported into a
   module (because the marker is not on `Test`).
6. `_public_methods` returns leaf-defined public methods in definition
   order.
7. `_public_methods` excludes methods whose name starts with `_`.
8. `_public_methods` includes inherited public methods from
   intermediate bases; leaf overrides win and appear in the leaf's
   position.

### `tests/test_runner.py` additions

9. Running a `Test` class with two passing public methods returns two
   `(bound_method, None)` entries with `__qualname__` values
   `ClassName.method_one` / `ClassName.method_two`.
10. Methods starting with `_` are not run.
11. `__enter__` runs once before the methods; `__exit__` runs once
    after — verified by a fixture class that records calls in a
    class-attribute list.
12. A failing assert in one method is recorded; the next method still
    runs; `__exit__` still runs.
13. An exception raised in `__enter__` propagates out of `run` (no
    methods run, `__exit__` is not called by `with`).
14. An exception raised in `__exit__` propagates out of `run`.
15. A module containing one `@test` function and one `Test` subclass
    yields combined results in `vars(module)` order.

### `tests/test_cli.py` additions

16. End-to-end run of a class fixture module produces lines beginning
    `ClassName.method_name ... ok` / `... FAIL:`.

### Fixtures

Under `tests/fixtures/runner/`:

- `class_simple.py` — one `Test` subclass with two passing methods.
- `class_with_underscore_methods.py` — `_helper`, `_data`, and one
  public method.
- `class_calls_recorded.py` — class with class-attribute list that
  records `__enter__` / `__exit__` calls and method calls.
- `class_method_fails.py` — one passing, one assert-fail method.
- `class_enter_raises.py` — `__enter__` raises `RuntimeError`.
- `class_exit_raises.py` — `__exit__` raises `RuntimeError`.
- `class_with_inheritance.py` — leaf class with one method,
  intermediate base with one method, plus an overridden method.
- `class_mixed_with_function.py` — module with one `@test` function
  and one `Test` subclass.

## Acceptance

- `from assertions import Test` succeeds.
- `examples/classes.py` (already in the repo) runs end-to-end via
  `uv run python -m assertions examples.classes`, prints
  `OrThings.or_dicts ... ok` and `OrThings.uses_database ... ok`,
  exits 0.
- All previous tests still pass.
- `uv run mypy` reports no issues.
