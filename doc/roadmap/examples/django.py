from assertions import test
from assertions.django import uses_db


# assertions.django.uses_db decorates functions and classes
@uses_db
@test
def there_is_a_superuser():
    assert User.objects.filter(is_superuser=True).exists()


@uses_db
@test
class ThereIsASuperuser:
    def there_is_a_superuser(self):
        assert User.objects.filter(is_superuser=True).exists()
