import importlib
import pathlib
import tempfile
import unittest

from assertions._targets import parse_target


_FIXTURES = pathlib.Path(__file__).resolve().parent / 'fixtures' / 'runner'


class TestParseTarget(unittest.TestCase):
    def test_dotted_module_no_selector(self):
        result = parse_target('tests.fixtures.runner.all_pass')
        self.assertEqual(len(result), 1)
        module, names = result[0]
        expected = importlib.import_module(
            'tests.fixtures.runner.all_pass',
        )
        self.assertIs(module, expected)
        self.assertIsNone(names)

    def test_relative_file_path(self):
        result = parse_target(
            'tests/fixtures/runner/all_pass.py',
        )
        self.assertEqual(len(result), 1)
        module, names = result[0]
        self.assertIsNone(names)
        self.assertTrue(hasattr(module, 'passes_one'))
        self.assertTrue(hasattr(module, 'passes_two'))

    def test_relative_file_path_with_dot(self):
        result = parse_target(
            './tests/fixtures/runner/all_pass.py',
        )
        self.assertEqual(len(result), 1)
        module, names = result[0]
        self.assertIsNone(names)
        self.assertTrue(hasattr(module, 'passes_one'))

    def test_absolute_file_path(self):
        path = (_FIXTURES / 'all_pass.py').resolve()
        result = parse_target(str(path))
        self.assertEqual(len(result), 1)
        module, names = result[0]
        self.assertIsNone(names)
        self.assertTrue(hasattr(module, 'passes_one'))

    def test_dotted_selector_one_segment(self):
        result = parse_target(
            'tests.fixtures.runner.all_pass.passes_one',
        )
        self.assertEqual(len(result), 1)
        module, names = result[0]
        expected = importlib.import_module(
            'tests.fixtures.runner.all_pass',
        )
        self.assertIs(module, expected)
        self.assertEqual(names, ['passes_one'])

    def test_dotted_selector_class_only(self):
        result = parse_target(
            'tests.fixtures.runner.class_simple.Simple',
        )
        self.assertEqual(len(result), 1)
        module, names = result[0]
        expected = importlib.import_module(
            'tests.fixtures.runner.class_simple',
        )
        self.assertIs(module, expected)
        self.assertEqual(names, ['Simple'])

    def test_dotted_selector_class_method(self):
        result = parse_target(
            'tests.fixtures.runner.class_simple.Simple.first',
        )
        self.assertEqual(len(result), 1)
        module, names = result[0]
        expected = importlib.import_module(
            'tests.fixtures.runner.class_simple',
        )
        self.assertIs(module, expected)
        self.assertEqual(names, ['Simple.first'])

    def test_dotted_too_many_segments(self):
        with self.assertRaises(LookupError):
            parse_target(
                'tests.fixtures.runner.class_simple.' 'Simple.first.extra',
            )

    def test_dotted_no_importable_prefix(self):
        with self.assertRaises(ModuleNotFoundError):
            parse_target('totally.not.a.module')

    def test_internal_import_error_propagates(self):
        with self.assertRaises(ModuleNotFoundError) as ctx:
            parse_target('tests.fixtures.runner.has_broken_import')
        self.assertEqual(
            ctx.exception.name,
            'this_dependency_does_not_exist',
        )


class TestParseTargetDirectory(unittest.TestCase):
    # parse_target on a directory imports each discovered .py file,
    # which adds entries to sys.modules. Snapshot and restore so
    # short-lived tmp-dir module names (`a`, `b`, etc.) don't leak
    # between tests and shadow each other on subsequent runs.

    def setUp(self):
        import sys

        self._saved_modules = dict(sys.modules)

    def tearDown(self):
        import sys

        for name in list(sys.modules):
            if name not in self._saved_modules:
                del sys.modules[name]

    def test_directory_yields_one_entry_per_py_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / 'a.py').write_text(
                'from assertions import test\n'
                '@test\n'
                'def t():\n'
                '    pass\n'
            )
            (root / 'b.py').write_text(
                'from assertions import test\n'
                '@test\n'
                'def t():\n'
                '    pass\n'
            )
            result = parse_target(str(root))
            self.assertEqual(len(result), 2)
            for module, names in result:
                self.assertIsNone(names)

    def test_nonexistent_directory_raises(self):
        with self.assertRaises((FileNotFoundError, ImportError)):
            parse_target('/this/path/really/should/not/exist/abc/')

    def test_empty_directory_returns_empty_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = parse_target(str(pathlib.Path(tmp)))
            self.assertEqual(result, [])


if __name__ == '__main__':
    unittest.main()
