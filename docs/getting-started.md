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
invocations:

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


Parametrized tests
------------------

Use `@test_params` to run the same test against multiple inputs:

```python
from testsweet import test_params


@test_params([
    ({'foo': 1}, {'bar': 2}, {'foo': 1, 'bar': 2}),
    ({'foo'}, {'bar'}, {'foo', 'bar'}),
    (0b01, 0b10, 0b11),
])
def or_things(thing1, thing2, expected):
    assert thing1 | thing2 == expected
```

If the parameter source is expensive to materialize and you only want
it consumed at run time, use `@test_params_lazy` instead.


Running tests
-------------

Testsweet ships a runner you invoke as a module:

```shell
python -m testsweet  # discover tests
python -m testsweet tests/test_module.py  # a file
python -m testsweet tests.test_module.TestClass.test_method  # a single test
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
