from testsweet import test
from testsweet.django import uses_db


# testsweet.django.uses_db decorates functions and classes
@uses_db
@test
def there_is_a_superuser():
    assert User.objects.filter(is_superuser=True).exists()


@uses_db
@test
class ThereIsASuperuser:
    def there_is_a_superuser(self):
        assert User.objects.filter(is_superuser=True).exists()
