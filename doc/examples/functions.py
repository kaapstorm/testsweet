from contextlib import contextmanager
from testsweet import test, test_params


# Tests are identified by the `test` decorator
@test
def or_dicts():
    assert {'foo': 1} | {'bar': 2} == {'foo': 1, 'bar': 2}


# pytest-style parametrized tests are supported
@test_params(
    [
        ({'foo': 1}, {'bar': 2}, {'foo': 1, 'bar': 2}),
        ({'foo'}, {'bar'}, {'foo', 'bar'}),
        (0b01, 0b10, 0b11),
    ]
)
def or_things(thing1, thing2, expected):
    assert thing1 | thing2 == expected


@test
def uses_database():
    # Use normal context managers for fixtures
    with db_fixture() as db:
        assert 'foo' in db
    assert 'foo' not in db


@contextmanager
def db_fixture():
    db = {'foo': 1}
    try:
        yield db
    finally:
        db.clear()
