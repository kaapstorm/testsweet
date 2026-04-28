import unittest


class ImportSmoke(unittest.TestCase):
    """Keeps `python -m unittest discover` green after the rest of the
    suite migrated to testsweet. If the testsweet package can't even
    be imported, this still fails — proving the dev tree is reachable
    via the stdlib runner."""

    def test_public_api_importable(self):
        import testsweet

        for name in (
            'ConfigurationError',
            'catch_exceptions',
            'catch_warnings',
            'discover',
            'run',
            'test',
            'test_params',
            'test_params_lazy',
        ):
            self.assertTrue(hasattr(testsweet, name), name)
