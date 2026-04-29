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

Running tests:

```shell
python -m testsweet tests.test_module.TestClass.test_method
python -m testsweet tests/test_module.py
python -m testsweet  # Discover tests
```


Documentation
-------------

* [Getting Started](https://github.com/kaapstorm/testsweet/blob/main/docs/getting-started.md)
* [Reference](https://github.com/kaapstorm/testsweet/blob/main/docs/reference.md)
* [Contributing](https://github.com/kaapstorm/testsweet/blob/main/docs/contributing.md)
