from assertions import test


@test
def decorated_one():
    pass


def undecorated():
    pass


@test
def decorated_two():
    pass
