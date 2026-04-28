Reference
=========

The public API of Testsweet, importable from the top-level
`testsweet` package.


Decorators
----------

### `test`

```python
from testsweet import test
```

Mark a function or class as a test unit.

Applied to a function, the function is discovered and run as a
standalone test. Applied to a class, the class is discovered and its
public methods (those not starting with `_`) are run as tests. If the
class implements the context-manager protocol — typically by
inheriting `contextlib.AbstractContextManager` — the runner enters it
for the duration of its method invocations.


### `test_params(args_iterable)`

```python
from testsweet import test_params
```

Run the decorated function once for each tuple in `args_iterable`.
The iterable is materialized eagerly at decoration time. Each tuple
is unpacked as positional arguments to the function.


### `test_params_lazy(args_iterable)`

```python
from testsweet import test_params_lazy
```

Like `test_params`, but the iterable is consumed at run time rather
than at decoration time. Use this when materializing the parameters
is expensive or has side effects that should be deferred.


Exception and warning capture
-----------------------------

### `catch_exceptions()`

```python
from testsweet import catch_exceptions
```

Context manager that captures exceptions raised inside its block.
Yields a list to which any caught `Exception` is appended; the
exception does not propagate.

```python
with catch_exceptions() as excs:
    1 / 0
assert type(excs[0]) is ZeroDivisionError
```


### `catch_warnings()`

```python
from testsweet import catch_warnings
```

Context manager that captures warnings emitted inside its block.
Yields a list to which each `Warning` is appended.

```python
import warnings

with catch_warnings() as warns:
    warnings.warn('use new_func', DeprecationWarning)
assert type(warns[0]) is DeprecationWarning
```


Discovery and running
---------------------

### `discover(module)`

```python
from testsweet import discover
```

Return the list of callables in `module` that are marked as tests.
Useful when embedding Testsweet in a custom runner.


### `run(module, names=None)`

```python
from testsweet import run
```

Run the tests in `module`. If `names` is given, only run tests
whose qualified names appear in the list. Returns a list of
`(name, exception_or_none)` tuples — `None` indicates success.


Errors
------

### `ConfigurationError`

```python
from testsweet import ConfigurationError
```

Raised when `[tool.testsweet.discovery]` in `pyproject.toml` contains
unknown keys or values of the wrong type.


Configuration keys
------------------

All keys live under `[tool.testsweet.discovery]` in `pyproject.toml`.

| Key             | Type           | Description                                     |
|-----------------|----------------|-------------------------------------------------|
| `include_paths` | list of string | Paths to search for tests.                      |
| `exclude_paths` | list of string | Paths to skip during discovery.                 |
| `test_files`    | list of string | Glob patterns identifying test modules.         |
