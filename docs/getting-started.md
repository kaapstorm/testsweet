Getting Started
===============

This guide walks through installing Testsweet, writing your first
tests, and running them.


Installing
----------

Testsweet runs on Python 3.11 or newer. Install it with your package
manager of choice:

```shell
pip install testsweet
```

Or, with [uv](https://docs.astral.sh/uv/):

```shell
uv add testsweet
```


Writing tests
-------------

Mark a function as a test with the `@test` decorator:

```python
from testsweet import test


@test
def or_dicts():
    assert {'foo': 1} | {'bar': 2} == {'foo': 1, 'bar': 2}
```

Group related tests on a class. The class itself is decorated with
`@test`; every public method is treated as a test:

```python
from testsweet import test


@test
class OrThings:
    def or_dicts(self):
        assert {'foo': 1} | {'bar': 2} == {'foo': 1, 'bar': 2}

    def or_sets(self):
        assert {'foo'} | {'bar'} == {'foo', 'bar'}
```

Methods whose names start with an underscore are treated as private
helpers and are not run as tests.


Fixtures
--------

Testsweet does not introduce a fixture system of its own. For
function-style tests, use any context manager:

```python
from contextlib import contextmanager
from testsweet import test


@contextmanager
def db_fixture():
    db = {'foo': 1}
    try:
        yield db
    finally:
        db.clear()


@test
def uses_database():
    with db_fixture() as db:
        assert 'foo' in db
```

For class-style tests, implement the context-manager protocol on the
class. The runner enters the class for the duration of its method
calls, so `__enter__()` and `__exit__()` methods are equivalent to
`setUpClass()` and `tearDownClass()` in unittest:

```python
from contextlib import AbstractContextManager
from testsweet import test


@test
class UsesDatabase(AbstractContextManager):
    def __enter__(self):
        self.db = {'foo': 1}
        return self

    def __exit__(self, exc_type, exc, tb):
        self.db.clear()
        return None

    def has_foo(self):
        assert 'foo' in self.db
```

For per-method setup/teardown (the equivalent of unittest's `setUp()`
and `tearDown()`), define `__test_context__` on the class. The runner
enters it once per test method, inside the class's `__enter__/__exit__`
scope:

```python
@test
class UsesDatabase(AbstractContextManager):
    def __enter__(self):
        self.db = {}
        return self

    def __exit__(self, exc_type, exc, tb):
        self.db.clear()
        return None

    @contextmanager
    def __test_context__(self):
        self.db['foo'] = 1
        try:
            yield
        finally:
            del self.db['foo']

    def has_foo(self):
        assert 'foo' in self.db
```

Subclasses can chain a parent's `__test_context__` via
`super().__test_context__()`.


Plugins
-------

Testsweet discovers plugins via the `testsweet.plugins` entry-point
group. A plugin is any module exposing both of:

* `session()` — a context manager that wraps the entire test run.
  Use for one-time setup/teardown (e.g. provisioning a test database).
* `unit(name)` — a context manager that wraps each test call. Use for
  per-test isolation.

Both are required. If a plugin doesn't need one, define a no-op:

```python
from contextlib import contextmanager


@contextmanager
def session():
    # ... real setup/teardown ...
    yield


@contextmanager
def unit(name):
    yield
```

Plugins are installed as ordinary Python distributions and register
themselves in their own `pyproject.toml`:

```toml
[project.entry-points."testsweet.plugins"]
django = "testsweet_django"
```

See [testsweet-django](https://github.com/kaapstrom/testsweet-django)
for a working example.


Parametrized tests
------------------

Stack `@test` with `@params` to run the same test against multiple
inputs:

```python
from testsweet import params, test


@test
@params([
    ({'foo': 1}, {'bar': 2}, {'foo': 1, 'bar': 2}),
    ({'foo'}, {'bar'}, {'foo', 'bar'}),
    (0b01, 0b10, 0b11),
])
def or_things(thing1, thing2, expected):
    assert thing1 | thing2 == expected
```

If the parameter source is expensive to materialize and you only want
it consumed at run time, use `@params_lazy` instead.

> **Migrating from 0.1.x:** the older single-decorator forms
> `@test_params` and `@test_params_lazy` were renamed to `@params` and
> `@params_lazy` in 0.2.0, and they no longer imply `@test`. Stack
> `@test` on top of `@params(...)` (or `@params_lazy(...)`) on the
> functions or methods you want discovered.


Skipping and expected failures
------------------------------

Mark a test as skipped with `@skip`. Without arguments, the test is
always skipped:

```python
from testsweet import skip, test


@test
@skip
def not_ready_yet():
    ...
```

Pass `reason=` to record why the test is skipped — the reason is
shown in the runner output:

```python
@test
@skip(reason='waiting on upstream fix')
def hits_broken_api():
    ...
```

Use `condition=` to skip conditionally. It accepts a bool or a
zero-arg callable; a callable is resolved at run time, so a function
reference does what you'd expect rather than being silently truthy:

```python
import sys


@test
@skip(condition=sys.platform == 'win32', reason='posix-only')
def uses_fork():
    ...


@test
@skip(condition=feature_flag_enabled, reason='disabled in this env')
def hits_feature():
    ...
```

`@xfail` marks a test as expected to fail. If it raises, the runner
reports `xfailed` and treats it as a pass for exit-code purposes:

```python
from testsweet import test, xfail


@test
@xfail(reason='regression in 0.2.0, see #123')
def known_bug():
    assert broken_thing() == 42
```

Testsweet's `@xfail` is **strict**: if a test marked `@xfail`
unexpectedly passes, the runner reports `XPASSED` and the run fails.
Either remove the marker (the bug is fixed) or fix the test.

`@xfail` also accepts `condition=` for conditional expected failure,
with the same bool-or-callable semantics as `@skip`.

When both `@skip` and `@xfail` are applied to the same test, `@skip`
wins — the test is reported as skipped and its body is not run.

The runner returns a `list[tuple[str, Outcome]]`, where `Outcome` is
one of `Passed`, `Failed`, `Errored`, `Skipped`, `XFailed`, or
`XPassed`. Tooling that inspects results can dispatch with `match`
or `isinstance`.


Tags
----

`@tag` attaches a free-form tag to a test:

```python
from testsweet import tag, test


@test
@tag('slow')
def big_integration_run():
    ...
```

Multiple tags stack:

```python
@test
@tag('slow')
@tag('network')
def hits_a_real_server():
    ...
```

A class-level `@tag` propagates to every method on the class. A
method's effective tag set is the union of its class's tags and its
own:

```python
@test
@tag('integration')
class HitsDatabase:
    def reads(self):       # tags: {'integration'}
        ...

    @tag('slow')
    def big_join(self):    # tags: {'integration', 'slow'}
        ...
```

Filter by tag at the command line:

```shell
testsweet -t slow                # run only @tag('slow') tests
testsweet -t db -t integration   # run tests tagged db OR integration
testsweet -T flaky               # skip @tag('flaky') tests
testsweet -t slow -T flaky       # slow but not flaky
```

`-t` / `--tag` and `-T` / `--exclude-tag` are repeatable. A test runs
iff it matches some `--tag` (or none was given) and has no
`--exclude-tag`. `--exclude-tag` is a hard veto: a test tagged with
both an included and an excluded tag is skipped.


Running tests
-------------

Testsweet installs a `testsweet` console script:

```shell
testsweet  # discover tests
testsweet tests/test_module.py  # a file
testsweet tests.test_module.TestClass.test_method  # a single test
```

The same runner is also reachable as a module (handy when the console
script is not on PATH, e.g. when running uninstalled from a checkout):

```shell
python -m testsweet
```

The runner prints one line per test and exits non-zero if any test
fails.


Configuration
-------------

Discovery can be configured in `pyproject.toml`:

```toml
[tool.testsweet.discovery]
include_paths = ["tests"]
exclude_paths = ["tests/fixtures"]
test_files = ["test_*.py", "*_test.py"]
```

See the [reference](reference.md) for the full list of public APIs.
