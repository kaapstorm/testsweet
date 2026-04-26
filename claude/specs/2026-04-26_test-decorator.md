# Design: `@test` decorator

## Scope

The first functional slice of the `assertions` package. Provides just enough
to make the first example in `README.md` import and run:

```python
from assertions import test

@test
def or_dicts():
    assert {'foo': 1} | {'bar': 2} == {'foo': 1, 'bar': 2}
```

Explicitly **out of scope** for this slice:

- Test discovery (walking modules / files)
- The `python -m assertions` runner
- `Test` base class, `test_params`, `assert_raises`, `assert_warns`
- Any override of, or introspection on, the `assert` statement —
  failures raise plain `AssertionError`

These are deferred to later slices.

## Approach

`@test` is a marker decorator. It sets a sentinel attribute on the function
and returns the function unchanged. A future discovery step will scan module
globals for objects carrying this attribute.

This is preferred over a module-level or package-level registry because:

- No mutable state in the package — decoration is a pure function
- Order of tests follows module dict insertion order, which is deterministic
  in Python 3.7+
- Re-imports do not produce duplicate registrations

## Module layout

| File                              | Purpose                              |
|-----------------------------------|--------------------------------------|
| `src/assertions/__init__.py`      | Re-export the public API (`test`)    |
| `src/assertions/_markers.py`      | Define `TEST_MARKER` and `test`      |

The marker name is exposed as a module-level constant so the eventual
discovery code reads from the same source as the decorator writes to.

## Behavior

```python
TEST_MARKER = "__assertions_test__"

def test(func):
    setattr(func, TEST_MARKER, True)
    return func
```

Properties:

- Returns the same function object (identity preserved)
- Sets `func.__assertions_test__ = True`
- Does not wrap, rename, or otherwise modify the function
- The decorated function remains directly callable with its normal
  signature and return value
- Permissive: `@test` does not validate what it is applied to. Misuse on
  classes or methods is a concern for the `Test` slice, not this one.

## Tests

Located under `tests/` (top-level), covering:

1. `@test` returns the same function object it was given (`is` check)
2. A decorated function has `__assertions_test__ == True`
3. A decorated function still runs and returns its normal return value
4. An undecorated function does not have the `__assertions_test__` attribute
5. The marker name is available as `assertions._markers.TEST_MARKER` and
   matches the attribute set by the decorator

Tests are written using the standard library `unittest` framework, since
the `assertions` runner does not yet exist.

## Acceptance

This slice is complete when:

- `from assertions import test` succeeds
- The first README example imports, decorates, and runs without error
- All tests above pass under `python -m unittest`
