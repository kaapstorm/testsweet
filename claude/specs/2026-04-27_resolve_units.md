# Design: extract `resolve_units` and shrink the runner

## Scope

Move two responsibilities out of `_runner.py`:

1. **Selector resolution** (`_build_plan`): validate user-supplied
   names against discovered units; raise `LookupError` for unmatched.
2. **Unit expansion**: turn each test unit (a function or a class)
   into an iterable of `(display_name, zero-arg-callable)` pairs,
   handling class-level fixtures, public-method enumeration, and
   parameter expansion.

These responsibilities go into a new `_resolve.py`. `_runner.py`
shrinks to a single try/except loop with no class-introspection or
marker-checking.

In scope:

- New `_resolve.py` with `resolve_units(module, names)` returning a
  list of generators.
- `_build_plan`, `_expand_unit`, `_expand_callable` move to
  `_resolve.py`.
- `_runner.py` rewritten to delegate.
- New `tests/test_resolve.py` with direct unit tests for the new
  function.
- Existing `tests/test_runner.py` is unchanged — its tests act as
  integration coverage for the new shape.

Out of scope:

- Renaming `run` or its return shape.
- Public API changes in `__init__.py`.
- Behavior change. Same units run, same display names, same exit
  codes. The order of operations (validate, then run) is preserved.

## Approach

The runner's current organization mixes three concerns:

```python
def run(module, names=None):
    units = discover(module)               # discovery
    if names is None:
        for unit in units:
            _run_unit(unit, None, results) # expansion + execution
        ...
    plan = _build_plan(units, names)       # resolution
    for unit in units:
        ...
        _run_unit(unit, method_filter, results)
```

Plus `_run_unit` and `_invoke` which together know about: classes,
context managers, public-method enumeration, the `PARAMS_MARKER`
attribute, and the iteration order of parameterized tests.

The new shape separates:

- **Resolve**: discovery, validation, expansion. Outputs a flat list
  of generators that yield `(name, callable)` pairs.
- **Execute**: iterate, call each callable, catch `Exception`, record.

A generator is the right shape for "expansion" because class-level
fixtures need a `with` block that brackets multiple method calls. A
generator with `with` inside it expresses that lifecycle naturally:
the context manager's `__enter__` runs at the first `next()`, and
`__exit__` runs when the generator is exhausted, closed, or
propagates an exception.

## Public surface

`resolve_units` is a private-internal function (`_resolve.py`). Its
signature:

```python
def resolve_units(
    module: ModuleType,
    names: list[str] | None = None,
) -> list[Iterator[tuple[str, Callable[[], None]]]]:
```

Returns a list of generators. Each generator corresponds to one
discovered test unit. Iterating a generator yields `(display_name,
no-arg-callable)` pairs ready for the runner to invoke.

The list is computed eagerly: `discover()` runs once, validation
runs once, all `LookupError` cases fire before any test runs. The
generators inside the list are lazy — they don't enter a context
manager or invoke a function until the runner iterates them.

## Behavior

### `resolve_units(module, names=None)`

1. Call `discover(module)` to get the list of marked units.
2. Call `_build_plan(units, names)` — returns
   `dict[unit_qualname, set[str] | None]`, raises `LookupError` if
   any name is unmatched.
3. For each unit:
   - Skip if `names is not None` and `unit.__qualname__` is not in
     the plan.
   - Otherwise, append `_expand_unit(unit, method_filter)` to the
     output list.
4. Return the list.

If `names is None`, no filtering happens — every discovered unit's
generator is included, with `method_filter=None`.

### `_expand_unit(unit, method_filter)`

A generator that yields `(name, callable)` pairs.

- If `unit` is a class (`isinstance(unit, type)`):
  - Instantiate once: `instance = unit()`.
  - Determine the context manager: `instance` itself if it has
    `__enter__`, otherwise `nullcontext(instance)`.
  - `with cm:` — enter the context.
  - For each method name in `_public_methods(unit)`, optionally
    filtered by `method_filter`, retrieve the bound method via
    `getattr(instance, method_name)` and `yield from
    _expand_callable(bound, bound.__qualname__)`.
- If `unit` is not a class, `yield from _expand_callable(unit,
  unit.__qualname__)`.

This is the only place that knows about classes, context managers,
public-method enumeration, and method filtering.

### `_expand_callable(func, qualname)`

A generator that yields `(name, callable)` pairs for one function or
bound method.

- If the function has no `PARAMS_MARKER` attribute: `yield (qualname,
  func)`. One pair.
- Otherwise, for each `(i, args)` in `enumerate(params)`:
  `yield (f'{qualname}[{i}]', functools.partial(func, *args))`.
  N pairs.

This is the only place that knows about `PARAMS_MARKER` and
`functools.partial`.

### `_build_plan(units, names)`

Moves verbatim from `_runner.py`. No body changes — the function is
already correct after the `Test`-class drop (uses `isinstance(unit,
type)`).

### `_runner.py` after the rewrite

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

About 15 lines including imports. The runner's responsibility is
visible at a glance: iterate, call, catch.

### Exception propagation rules — preserved

- `__enter__` raises → first `next()` on the generator propagates
  the exception. The runner's outer for-loop is iteration, not
  inside a try, so the exception propagates out of `run`. (Matches
  current spec: fixture errors are not test failures.)
- A method raises `Exception` → caught by the inner try/except,
  recorded as a test failure, the loop continues to the next
  yielded callable.
- A method raises `BaseException` (e.g. `KeyboardInterrupt`) → not
  caught. Propagates through the generator's yield, triggers the
  `with` block's `__exit__(BaseException, ...)`, and propagates out
  of `run`.
- `__exit__` raises after normal iteration → propagates from the
  final `next()` (which would otherwise raise `StopIteration`),
  propagates out of `run`.

These match the existing test expectations in
`tests/test_runner.py` (`test_enter_exception_propagates`,
`test_exit_exception_propagates`, etc.).

## Module layout

| File | Action | Purpose |
|------|--------|---------|
| `src/assertions/_resolve.py` | create | `resolve_units`, `_expand_unit`, `_expand_callable`, `_build_plan` |
| `src/assertions/_runner.py` | rewrite | `run` only (~15 lines) |
| `tests/test_resolve.py` | create | Direct unit tests for `resolve_units` |

No deletions; no other source files touched. No test moves —
`tests/test_runner.py` keeps every test as integration coverage.

## Tests

### `tests/test_resolve.py` (new)

Each test exercises `resolve_units` directly. Most consume the
returned generators with `list()` to materialize all yielded pairs.

1. **One unit, one pair**: a module with a single plain `@test`
   function returns one generator. The generator yields exactly
   one `(qualname, func)` pair where `func` is the function itself.
2. **Parameterized function**: a module with a `@test_params([(1,),
   (2,)])` function returns one generator. The generator yields
   two pairs with names `func[0]` and `func[1]`. Each callable is
   a `functools.partial` (verify by inspecting; or by calling and
   checking observed args via a probe).
3. **Class with public methods, no context manager**: instantiate
   counter; verify the instance is created exactly once, and each
   method's bound form is yielded with `Class.method` qualname.
4. **Class with context manager**: a class implementing
   `__enter__`/`__exit__` (e.g., subclass of
   `contextlib.AbstractContextManager`) records call order. After
   consuming the generator: `enter` happens once before any method
   yield, `exit` happens once after the last yield.
5. **Selector filtering inside a class**: `names=['Cls.first']`
   yields only `Cls.first`; `Cls.second` is skipped.
6. **`LookupError` for unmatched name**: `names=['nonexistent']`
   raises `LookupError` before returning. The error message
   includes the unmatched name.
7. **Validation runs before iteration**: when one name is matched
   and another is unmatched, the matched unit's generator is NOT
   iterated (verifiable because `LookupError` raises before
   `resolve_units` returns).
8. **Class form wins over selector for the same class**: `names=
   ['Cls', 'Cls.first']` yields all of `Cls`'s methods, not just
   `first`.
9. **Mixed module**: a module with both a `@test` function and a
   `@test` class returns two generators in `vars(module)`-insertion
   order. Each yields its own pairs.
10. **Empty module**: `resolve_units(module_with_no_marked_units)`
    returns `[]`.

### `tests/test_runner.py` (unchanged)

Every test in this file goes through `run(module, ...)` and asserts
on the returned `(name, exc)` list. Behavior is unchanged, so all
tests continue to pass.

## Acceptance

- `src/assertions/_runner.py` is ~15 lines and contains no `Test`
  detection, no class introspection, no `PARAMS_MARKER` reference,
  no `_build_plan`.
- `src/assertions/_resolve.py` owns `resolve_units`, `_expand_unit`,
  `_expand_callable`, `_build_plan`.
- All previous tests pass (current count 145; resolve tests add ~10
  for a final count around 155).
- `uv run mypy` reports no issues.
- The CLI's behavior is unchanged for every existing scenario.
