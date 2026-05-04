from testsweet._tag import tag


@tag('slow')
def orphan():
    assert True
