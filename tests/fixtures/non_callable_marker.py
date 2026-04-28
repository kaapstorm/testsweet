from testsweet._markers import TEST_MARKER


class _Marked:
    pass


fake = _Marked()
setattr(fake, TEST_MARKER, True)
