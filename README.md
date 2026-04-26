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

Running tests:

```shell
python -m assertions tests.test_module.TestClass.test_method
python -m assertions tests/test_module.py
python -m assertions  # Discover tests
```
