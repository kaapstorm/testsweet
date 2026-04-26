from assertions import test


@test
def interrupts():
    raise KeyboardInterrupt
