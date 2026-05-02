from contextlib import contextmanager

from django.contrib.auth.models import User

from testsweet import test, catch_exceptions
from testsweet.django import TestCase, databases


@test
class ExampleClassWithModelFixture(TestCase):
    def __enter__(self):
        self = super().__enter__()
        self.user = User.objects.create(username='testy', password='Passw0rd!')
        return self

    def __exit__(self, exc_type, exc, tb):
        self.user.delete()
        return super().__exit__(exc_type, exc, tb)

    def check_user(self):
        testy = User.objects.get(username='testy')
        assert self.user.username == testy.username


@test
def example_func_with_model_fixture():
    with user_fixture() as user:
        assert user.username == 'testy'


@test
def example_with_databases():
    with databases():
        assert User.objects.count() == 0
        with user_fixture():
            all_usernames = [u.username for u in User.objects.all()]
            assert all_usernames == ['testy']
        assert User.objects.count() == 0


@contextmanager
def user_fixture():
    with databases():
        user = User.objects.create(username='testy', password='Passw0rd!')
        try:
            yield user
        finally:
            user.delete()
