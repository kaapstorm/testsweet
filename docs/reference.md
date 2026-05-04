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

If the class defines a `__test_context__` method returning a context
manager, the runner enters it once per test method, inside the
class's `__enter__/__exit__` scope. This is the equivalent of
unittest's `setUp()` and `tearDown()`. Subclasses can chain a parent
implementation via `super().__test_context__()`.


### `params(args_iterable)`

```python
from testsweet import params, test
```

Run the decorated function once for each tuple in `args_iterable`.
The iterable is materialized eagerly at decoration time. Each tuple
is unpacked as positional arguments to the function. Stack with
`@test` to register the function for discovery:

```python
@test
@params([(1, 2, 3), (4, 5, 9)])
def adds(a, b, expected):
    assert a + b == expected
```


### `params_lazy(args_iterable)`

```python
from testsweet import params_lazy, test
```

Like `params`, but the iterable is consumed at run time rather than
at decoration time. Use this when materializing the parameters is
expensive or has side effects that should be deferred.


### `skip`

```python
from testsweet import skip, test
```

Mark a test as skipped. Bare `@skip` always skips. Called as
`@skip(reason='…')` it records a human-readable reason; called as
`@skip(if_=condition)` it skips only when `condition` is truthy.

```python
@test
@skip(if_=sys.platform == 'win32', reason='posix-only')
def uses_fork():
    ...
```


### `xfail`

```python
from testsweet import test, xfail
```

Mark a test as expected to fail. If the test raises, the runner
reports `XFAIL`; if it unexpectedly passes, the runner reports
`XPASS` and the run fails (testsweet's `@xfail` is strict).

Like `@skip`, `@xfail` accepts `reason=` and `if_=`:

```python
@test
@xfail(reason='regression #123')
def known_bug():
    assert broken_thing() == 42
```


### `tag(name)`

```python
from testsweet import tag, test
```

Attach a free-form tag to a test. Multiple `@tag` decorators stack.
Tags are stored on the test for tooling to inspect; testsweet does
not currently filter by tag from the command line.

```python
@test
@tag('slow')
@tag('network')
def hits_a_real_server():
    ...
```


Outcome sentinels
-----------------

The runner constructs (does not raise) one of these classes and
places it in the exception slot of the result tuple returned by
`run()`. They subclass `Exception` so the result-tuple shape is
unchanged. Tooling distinguishes them with `isinstance`.

### `Skipped`

```python
from testsweet import Skipped
```

Placed when an active `@skip` marker matched. Carries a `reason`
attribute (may be `None`).

### `XFailed`

```python
from testsweet import XFailed
```

Placed when an `@xfail`-marked test raised the expected failure.
Carries the underlying exception as `actual` and the marker's
`reason`.

### `XPassed`

```python
from testsweet import XPassed
```

Placed when an `@xfail`-marked test unexpectedly passed. Treated as
a failure for exit-code purposes.


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


### `run(module, names=None, wrap_unit=None)`

```python
from testsweet import run
```

Run the tests in `module`. If `names` is given, only run tests
whose qualified names appear in the list. If `wrap_unit` is given,
each test call is wrapped in `wrap_unit(name)`, which must return a
context manager. Returns a list of `(name, exception_or_none)`
tuples — `None` indicates a regular pass.

The exception slot may also hold a `Skipped`, `XFailed`, or
`XPassed` sentinel for tests marked with `@skip` or `@xfail`. Use
`isinstance` to distinguish these from genuine failures.


Plugins
-------

Plugins are discovered via the `testsweet.plugins` entry-point group.
A plugin is any module-like object exposing both of:

* `session()` — a context manager wrapping the entire test run.
* `unit(name)` — a context manager wrapping each test call.

Both are required. A plugin missing either hook is rejected at load
time with a `ConfigurationError`. If a plugin doesn't need one,
define a no-op:

```python
from contextlib import contextmanager


@contextmanager
def unit(name):
    yield
```

Plugins are ordinary Python distributions; they register themselves
in their own `pyproject.toml`:

```toml
[project.entry-points."testsweet.plugins"]
django = "testsweet_django"
```

Plugins are entered in entry-point iteration order. Each plugin's
`session()` and `unit()` is a context manager; exceptions propagate
normally and `__exit__` is not expected to suppress.

### Trust

Plugins are arbitrary Python code, executed at testsweet startup.
Installing a plugin from PyPI is a trust decision equivalent to
installing any other dependency — testsweet does not sandbox or
allowlist plugins.


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

| Key             | Type           | Description                             |
|-----------------|----------------|-----------------------------------------|
| `include_paths` | list of string | Paths to search for tests.              |
| `exclude_paths` | list of string | Paths to skip during discovery.         |
| `test_files`    | list of string | Glob patterns identifying test modules. |
