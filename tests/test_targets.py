import importlib
import pathlib
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


if __name__ == '__main__':
    unittest.main()
