from testsweet import test


@test
def interrupts():
    raise KeyboardInterrupt
