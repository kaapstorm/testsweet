from assertions import test


@test
def raises_value_error():
    raise ValueError('boom')
