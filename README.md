Assertions
==========

Python testing for humans


Examples
--------

A test function:

```python
from assertions import test


@test
def or_dicts():
    assert {'foo': 1} | {'bar': 2} == {'foo': 1, 'bar': 2}
```

A test class:

```python
from assertions import Test

class OrThings(Test):
    def or_dicts(self):
        assert {'foo': 1} | {'bar': 2} == {'foo': 1, 'bar': 2}
```

Catching exceptions and warnings:

```python
import warnings
from assertions import catch_exceptions, catch_warnings, test


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
python -m assertions tests.test_module.TestClass.test_method
python -m assertions tests/test_module.py
python -m assertions  # Discover tests
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
