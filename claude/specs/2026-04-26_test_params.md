# Design: `test_params` / `test_params_lazy` and result-shape refactor

## Scope

Add two parameterizing decorators that turn a single function
definition into multiple invocations:

- `@test_params(args_iterable)` — eager. Materializes the iterable
  into a tuple at decoration time. Idempotent across `run()` calls.
- `@test_params_lazy(args_iterable)` — lazy. Stores the iterable
  unchanged. Iterated at run time. **Single-shot**: if a generator is
  passed, a second `run()` will see no params for that function.

While touching the runner anyway, refactor the result shape from
`(callable, exc_or_None)` to `(name: str, exc_or_None)` and have the
runner produce display names itself. `_public_methods` becomes a
`list[str]` of method names.

In scope:

- Both decorators on free functions.
- Both decorators on public methods of `Test` subclasses. The runner
  handles all four combinations uniformly via a single dispatch path.

Out of scope for this slice:

- Custom invocation IDs / labels (`ids=` à la pytest).
- `dict`-style param expansion (kwargs).
- A callable-returns-iterable variant (re-evaluating params on each
  `run()` invocation by calling a producer function).
- Anything that needs the callable inside a result (re-run, IDE jump,
  rich traceback formatting). The exception's `__traceback__` is the
  primary signal for future failure reporting and does not require the
  callable.
- File-path / package-walk discovery, bare auto-discovery, selectors,
  `assert_raises`, `assert_warns`.

## Approach

Both decorators set `TEST_MARKER = True` and store an iterable under a
shared `PARAMS_MARKER = '__assertions_params__'` attribute on the
function. The only difference is what they store:

- `test_params` materializes the iterable into a tuple at decoration
  time, then stores the tuple. Generators are fully consumed at import
  time. Subsequent `run()` calls iterate the same tuple → idempotent
  results.
- `test_params_lazy` stores the iterable as-is. The runner iterates it
  at run time. If the iterable is a generator, it is consumed on first
  run; subsequent `run()` calls see an exhausted generator and produce
  no results for that function.

The runner does not distinguish the two — it just iterates whatever is
stored. The decorator the user picks is the only opt-in for lazy
semantics.

The runner gains one branch in its function-or-method invocation step:
if the callable has a `PARAMS_MARKER` attribute, iterate the stored
value and call `func(*tuple)` once per entry, generating result names
of the form `<qualname>[<i>]`. Otherwise, call the callable once with
no args (existing behavior).

The result list shape changes from
`list[tuple[Callable, Exception | None]]` to
`list[tuple[str, Exception | None]]`. The runner produces all display
names — the CLI no longer touches `__qualname__`.

`_public_methods` returns `list[str]` (method names) instead of
`list[Callable]`. The runner does the binding via
`getattr(instance, name)`.

## Public surface

```python
from assertions import test_params, test_params_lazy


@test_params([
    (1, 2, 3),
    (4, 5, 9),
])
def adds(a, b, expected):
    assert a + b == expected


def get_triples():
    for i in range(3):
        yield (3 * i, 3 * i + 1, 3 * i + 3)


@test_params_lazy(get_triples())
def are_triples(a, b, c):
    assert a + 2 == b + 1 == c
```

Properties (both decorators):

- `func.__assertions_test__` is `True` (so `discover` picks it up).
- `func.__assertions_params__` is the stored iterable: a tuple for
  `test_params`, the original iterable for `test_params_lazy`.
- `func(*args)` still calls the function directly.
- Stacking with `@test` is allowed but redundant.
- Stacking the two parameter decorators on the same function is
  undefined behavior — the inner one wins by virtue of being applied
  first; the outer overrides. Don't.

## Behavior

### `@test_params` (eager)

```python
PARAMS_MARKER = '__assertions_params__'


def test_params(args_iterable):
    materialized = tuple(args_iterable)

    def decorator(func):
        setattr(func, TEST_MARKER, True)
        setattr(func, PARAMS_MARKER, materialized)
        return func
    return decorator
```

- The supplied iterable is materialized to a tuple at decoration time.
  Generators are exhausted; lists and tuples are copied.
- Once stored, the params tuple is immutable. `run()` calls are
  idempotent — repeated calls iterate the same tuple.

### `@test_params_lazy` (lazy)

```python
def test_params_lazy(args_iterable):
    def decorator(func):
        setattr(func, TEST_MARKER, True)
        setattr(func, PARAMS_MARKER, args_iterable)
        return func
    return decorator
```

- The supplied iterable is stored as-is. The runner iterates it at run
  time.
- **Single-shot semantics:** if `args_iterable` is a one-shot iterator
  (e.g., a generator), the first `run()` consumes it and subsequent
  `run()` calls produce no results for this function. This is the
  explicit trade-off the user accepts by picking the `lazy` variant.
- Reusable iterables (e.g., a list, a class with `__iter__`) work
  fine across multiple `run()` calls — each call gets fresh iteration.

### Common rules (both decorators)

- The runner unpacks each item with `*`, so each item must itself be a
  tuple-or-iterable of positional args matching the function's
  signature. A single-arg test must use one-tuples (`[(1,), (2,)]`),
  not bare values.

### Runner

The runner's invocation step becomes uniform across function and bound
method paths:

```python
def _invoke(callable, qualname, results):
    params = getattr(callable, PARAMS_MARKER, None)
    if params is None:
        try:
            callable()
        except Exception as exc:
            results.append((qualname, exc))
        else:
            results.append((qualname, None))
    else:
        for i, args in enumerate(params):
            name = f'{qualname}[{i}]'
            try:
                callable(*args)
            except Exception as exc:
                results.append((name, exc))
            else:
                results.append((name, None))
```

The function path passes `unit` and `unit.__qualname__`. The class
path binds methods via `getattr(instance, method_name)` and passes the
bound method together with `bound.__qualname__` (which is
`ClassName.method_name`).

### `_public_methods`

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

Same MRO walk and filter rules as before; just yields names instead of
callables.

### Result shape

`run(module) -> list[tuple[str, Exception | None]]`. The first element
of each tuple is the display name (e.g., `or_dicts`,
`OrThings.or_dicts`, `or_things[0]`). The second element is the same
`Exception | None` as before — the exception preserves its full
`__traceback__` so future CLI changes can render it.

### CLI

`__main__.py` no longer references `__qualname__`:

```python
for name, exc in results:
    if exc is None:
        print(f'{name} ... ok')
    else:
        print(f'{name} ... FAIL: {type(exc).__name__}: {exc}')
```

Exit-code rule unchanged.

## Module layout

| File | Action | Purpose |
|------|--------|---------|
| `src/assertions/_params.py` | create | `test_params` and `test_params_lazy` decorators + `PARAMS_MARKER` |
| `src/assertions/_runner.py` | modify | Switch to `(name, exc)` results; param dispatch; uniform `_invoke` |
| `src/assertions/_test_class.py` | modify | `_public_methods` returns `list[str]` |
| `src/assertions/__main__.py` | modify | Drop `__qualname__` use |
| `src/assertions/__init__.py` | modify | Re-export `test_params` and `test_params_lazy` |

`_params.py` is its own module because it owns the `PARAMS_MARKER`
constant and both decorators. Keeping it separate from `_markers.py`
preserves the rule that `_markers.py` is just for the bare test
marker.

## Tests

### `tests/test_params.py` (new)

For `@test_params` (eager):

1. Returns the same function object.
2. Decorated function has `__assertions_test__ == True`.
3. Decorated function has `__assertions_params__` equal to a tuple
   matching the supplied iterable.
4. Passing a generator: stored value is a tuple of yielded items
   (verifies eager materialization).
5. The decorated function is still directly callable with positional
   args.

For `@test_params_lazy` (lazy):

6. Returns the same function object.
7. Decorated function has `__assertions_test__ == True`.
8. Decorated function has `__assertions_params__` that **is** the
   supplied object (identity check — not materialized).
9. Passing a generator: `__assertions_params__` is the generator
   itself, not a tuple.
10. The decorated function is still directly callable with positional
    args.

### `tests/test_runner.py` (modify)

Update existing tests to read `(name, exc)` instead of `(func, exc)`:

- `test_single_passing_test` — assert all names in
  `['passes_one', 'passes_two']`.
- `test_single_failing_assert` — assert names `['passes', 'fails']`.
- `test_results_in_discover_order` — names `['passes', 'fails']`.
- `test_empty_module_returns_empty_list` — unchanged.
- `test_non_assertion_exception_is_caught` — name
  `'raises_value_error'`.
- `test_keyboard_interrupt_propagates` — unchanged.
- `test_class_with_passing_methods` — names
  `['Simple.first', 'Simple.second']`.
- `test_underscore_methods_are_skipped` — name `['public']`.
- `test_enter_and_exit_run_around_methods` — unchanged.
- `test_failing_method_does_not_abort_class` — names
  `['HasFailure.passes', 'HasFailure.fails']`.
- `test_enter_exception_propagates` / `test_exit_exception_propagates`
  — unchanged.
- `test_mixed_function_and_class_in_vars_order` — names
  `['free_function', 'ClassUnit.method']`.

Add new tests for `test_params`:

- `test_params_runs_each_tuple` — module with
  `@test_params([(1, 1, 2), (2, 3, 5)])` produces two results in
  order, names `['adds[0]', 'adds[1]']`, both pass.
- `test_params_failures_recorded_per_tuple` — failing tuple yields a
  result with `AssertionError` at the right index; passing tuples
  remain `None`.
- `test_params_empty_list_produces_no_results` — `@test_params([])`
  decoration: discover sees the function (it's marked), but `run`
  produces zero results for it.
- `test_function_without_params_unchanged` — sanity: existing
  `@test`-decorated function still produces a single
  `(qualname, None)` entry.
- `test_params_accepts_generator` — a function decorated with
  `@test_params` over a generator runs once per yielded tuple. Calling
  `run` a second time still produces the same results (the generator
  was consumed at decoration time, so the stored tuple is reused).
- `test_params_on_class_method` — a `Test` subclass with a method
  decorated `@test_params([(1,), (2,)])` produces results
  `['Cls.method[0]', 'Cls.method[1]']` in order, both passing.
- `test_params_lazy_runs_each_yielded_tuple` — a function decorated
  with `@test_params_lazy(get_args())` runs once per yielded tuple on
  the first `run()` call.
- `test_params_lazy_is_consumed_after_first_run` — a generator-backed
  `@test_params_lazy` function: first `run(module)` produces N
  results, second `run(module)` produces zero results for that
  function. Other tests in the module are unaffected.
- `test_params_lazy_with_list_is_idempotent` — a list-backed
  `@test_params_lazy` function: repeated `run(module)` produces the
  same results each time (lists are reusable iterables).
- `test_params_lazy_on_class_method` — a `Test` subclass with a
  method decorated `@test_params_lazy([(1,), (2,)])` produces results
  `['Cls.method[0]', 'Cls.method[1]']` in order, both passing.

### `tests/test_test_class.py` (modify)

Adjust the existing `_public_methods` tests to compare against
`list[str]` directly rather than `[f.__name__ for f in ...]`:

- `test_returns_leaf_methods_in_definition_order`
- `test_excludes_underscore_prefixed_methods`
- `test_includes_inherited_methods_with_leaf_priority`
- `test_diamond_inheritance_follows_mro`
- `test_staticmethod_is_included`
- `test_classmethod_is_excluded`

### `tests/test_cli.py` (modify)

No assertions need to change — the existing assertions search for
substrings like `passes_one ... ok` and `Simple.first ... ok`, both of
which the new code path still produces. Add one new test:

- `test_parameterized_indices_in_output` — invoking the CLI on a
  fixture with `@test_params([...])` shows lines like `adds[0] ... ok`
  and `adds[1] ... ok`.

### Fixtures (new under `tests/fixtures/runner/`)

- `params_simple.py` — one function decorated with
  `@test_params([(1, 1, 2), (2, 3, 5)])`.
- `params_with_failure.py` — one function with three tuples, the
  middle one failing.
- `params_empty.py` — one function decorated with `@test_params([])`.
- `params_no_decoration.py` — sanity fixture: one plain `@test`
  function next to a `@test_params` function, used by
  `test_function_without_params_unchanged`.
- `params_generator.py` — function decorated with `@test_params`
  fed a generator expression yielding three tuples.
- `params_on_class_method.py` — `Test` subclass with one method
  decorated `@test_params([(1,), (2,)])`.
- `params_lazy_generator.py` — function decorated with
  `@test_params_lazy(get_args())`, where `get_args` yields three
  tuples. Used to verify single-shot consumption.
- `params_lazy_list.py` — function decorated with
  `@test_params_lazy([(1, 1), (2, 2)])`. Used to verify that a list
  is re-iterable across runs.
- `params_lazy_on_class_method.py` — `Test` subclass with one method
  decorated `@test_params_lazy([(1,), (2,)])`.

## Acceptance

- `from assertions import test_params, test_params_lazy` succeeds.
- `examples/functions.py` runs end-to-end via
  `uv run python -m assertions examples.functions` and prints lines
  for `or_dicts`, `or_things[0]`, `or_things[1]`, `or_things[2]`, and
  `uses_database`. Exit code 0.
- All previous tests pass after the result-shape refactor.
- `uv run mypy` reports no issues.
