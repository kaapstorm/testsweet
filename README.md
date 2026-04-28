Testsweet
=========

Python testing for humans


Why?
----

Neither of the two most popular libraries for testing in Python,
[unittest](https://docs.python.org/3/library/unittest.html) and
[pytest](https://docs.pytest.org/), make it over the hurdle of the Zen
of Python.

```
Beautiful is better than ugly.
Explicit is better than implicit.
```

unittest is modeled closely on JUnit and the xUnit family of libraries.
Its strength is its familiarity to people who are accustomed to them.
Its weakness is its failure to take advantage of existing Python idioms
and conventions. It's not beautiful.

Pytest addresses a lot of the shortcomings of unittest, but the way that
[its fixtures](https://docs.pytest.org/en/stable/how-to/fixtures.html)
work is magical, especially when they are imported
[invisibly](https://docs.pytest.org/en/stable/how-to/writing_plugins.html#localplugin).
It doesn't make it past the second line of the Zen of Python.

Testsweet intends to be a Python testing library that uses existing
Python features and idioms: A kind and simple interface, explicit in its
architecture, enabling the tests that use it to be beautiful.


Examples
--------

A test function:

```python
from testsweet import test


@test
def or_dicts():
    assert {'foo': 1} | {'bar': 2} == {'foo': 1, 'bar': 2}
```

A test class:

```python
from testsweet import test


@test
class OrThings:
    def or_dicts(self):
        assert {'foo': 1} | {'bar': 2} == {'foo': 1, 'bar': 2}
```

Catching exceptions and warnings:

```python
import warnings
from testsweet import catch_exceptions, catch_warnings, test


@test
def zero_div():
    with catch_exceptions() as excs:
        1 / 0
    assert type(excs[0]) is ZeroDivisionError


@test
def deprecated():
    with catch_warnings() as warns:
        warnings.warn('use new_func', DeprecationWarning)
    assert type(warns[0]) is DeprecationWarning
    assert 'new_func' in str(warns[0])
```

Running tests:

```shell
python -m testsweet tests.test_module.TestClass.test_method
python -m testsweet tests/test_module.py
python -m testsweet  # Discover tests
```


Installing
----------

This project uses [uv](https://docs.astral.sh/uv/) for dependency and
environment management.

Sync the project (creates a virtualenv and installs dependencies,
including the `dev` group):

```shell
uv sync
```

Activate the pre-commit hook so `ruff format` runs automatically before
each commit:

```shell
uv run pre-commit install
```
