import importlib
import pathlib
import unittest

from assertions._targets import parse_target


_FIXTURES = pathlib.Path(__file__).resolve().parent / 'fixtures' / 'runner'


class TestParseTarget(unittest.TestCase):
    def test_dotted_module_no_selector(self):
        module, names = parse_target('tests.fixtures.runner.all_pass')
        expected = importlib.import_module(
            'tests.fixtures.runner.all_pass',
        )
        self.assertIs(module, expected)
        self.assertIsNone(names)

    def test_relative_file_path(self):
        module, names = parse_target(
            'tests/fixtures/runner/all_pass.py',
        )
        self.assertIsNone(names)
        self.assertTrue(hasattr(module, 'passes_one'))
        self.assertTrue(hasattr(module, 'passes_two'))

    def test_relative_file_path_with_dot(self):
        module, names = parse_target(
            './tests/fixtures/runner/all_pass.py',
        )
        self.assertIsNone(names)
        self.assertTrue(hasattr(module, 'passes_one'))

    def test_absolute_file_path(self):
        path = (_FIXTURES / 'all_pass.py').resolve()
        module, names = parse_target(str(path))
        self.assertIsNone(names)
        self.assertTrue(hasattr(module, 'passes_one'))

    def test_dotted_selector_one_segment(self):
        module, names = parse_target(
            'tests.fixtures.runner.all_pass.passes_one',
        )
        expected = importlib.import_module(
            'tests.fixtures.runner.all_pass',
        )
        self.assertIs(module, expected)
        self.assertEqual(names, ['passes_one'])

    def test_dotted_selector_class_only(self):
        module, names = parse_target(
            'tests.fixtures.runner.class_simple.Simple',
        )
        expected = importlib.import_module(
            'tests.fixtures.runner.class_simple',
        )
        self.assertIs(module, expected)
        self.assertEqual(names, ['Simple'])

    def test_dotted_selector_class_method(self):
        module, names = parse_target(
            'tests.fixtures.runner.class_simple.Simple.first',
        )
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


if __name__ == '__main__':
    unittest.main()
