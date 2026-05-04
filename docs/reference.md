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
`@skip(condition=expr)` it skips only when `expr` resolves truthy.
`condition=` accepts a bool or a zero-arg callable; a callable is
invoked by the runner at run time.

```python
@test
@skip(condition=sys.platform == 'win32', reason='posix-only')
def uses_fork():
    ...
```

When both `@skip` and `@xfail` are applied to the same test, `@skip`
wins — the test is reported as skipped and its body is not run.


### `xfail`

```python
from testsweet import test, xfail
```

Mark a test as expected to fail. If the test raises, the runner
reports `xfailed`; if it unexpectedly passes, the runner reports
`XPASSED` and the run fails (testsweet's `@xfail` is strict).

Like `@skip`, `@xfail` accepts `reason=` and `condition=` with
identical semantics:

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

Attach a free-form tag to a test. Multiple `@tag` decorators stack
(set-union). A class-level `@tag` propagates to every method on the
class — a method's effective tag set is the union of its class's
tags and its own.

```python
@test
@tag('slow')
@tag('network')
def hits_a_real_server():
    ...
```

The CLI accepts `-t`/`--tag` and `-T`/`--exclude-tag` to filter by
tag; both flags are repeatable. A test runs iff it matches some
`--tag` (or none was given) AND has no `--exclude-tag`.
`--exclude-tag` is a hard veto.

```shell
testsweet -t slow -T flaky
```

The `run()` function exposes the same filter via the `keep=` kwarg,
which takes a `Callable[[frozenset[str]], bool]`.


Outcomes
--------

`run()` returns a `list[tuple[str, Outcome]]`. `Outcome` is a sum of
the six frozen dataclasses below — values, not exceptions. Tooling
dispatches with `match` or `isinstance`.

```python
from testsweet import (
    Outcome, Passed, Failed, Errored, Skipped, XFailed, XPassed,
)
```

### `Passed`

The test ran and returned without raising. No fields.

### `Failed`

The test raised `AssertionError`. Carries the exception as `exc`.

### `Errored`

The test raised an exception other than `AssertionError`, or a
callable `condition=` on `@skip`/`@xfail` raised while the runner
was evaluating it. Carries the exception as `exc`.

### `Skipped`

An active `@skip` marker matched. Carries `reason: str | None`.

### `XFailed`

An `@xfail`-marked test raised the expected failure. Carries the
underlying exception as `actual` and the marker's `reason`.

### `XPassed`

An `@xfail`-marked test unexpectedly passed. Treated as a failure
for exit-code purposes. Carries `reason`.


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


### `run(module, names=None, wrap_unit=None, keep=None)`

```python
from testsweet import run
```

Run the tests in `module`. If `names` is given, only run tests
whose qualified names appear in the list. If `wrap_unit` is given,
each test call is wrapped in `wrap_unit(name)`, which must return a
context manager. If `keep` is given, each test's effective tag set
(class tags ∪ method tags) is passed to it and the test runs only
when the predicate returns truthy. Returns a
`list[tuple[str, Outcome]]` — see [Outcomes](#outcomes) for the
variants.


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

### Known plugins

* [testsweet-django](https://github.com/kaapstorm/testsweet-django/) is
  the first plugin and example implementation. 


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
