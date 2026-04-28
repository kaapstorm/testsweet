import contextlib
import importlib
import pathlib
import sys
import tempfile
import unittest

from testsweet._config import DiscoveryConfig
from testsweet._targets import discover_targets, parse_target


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
                'from testsweet import test\n'
                '@test\n'
                'def t():\n'
                '    pass\n'
            )
            (root / 'b.py').write_text(
                'from testsweet import test\n'
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


class TestDiscoverTargets(unittest.TestCase):
    # discover_targets imports test modules from temp directories,
    # which leaves entries in sys.modules. Snapshot/restore so
    # short-lived tmp-dir module names don't leak between tests.

    def setUp(self):
        self._saved_modules = dict(sys.modules)

    def tearDown(self):
        for name in list(sys.modules):
            if name not in self._saved_modules:
                del sys.modules[name]

    def test_single_dotted_module(self):
        config = DiscoveryConfig()
        groups = discover_targets(
            ['tests.fixtures.runner.all_pass'],
            config,
        )
        self.assertEqual(len(groups), 1)
        module, names = groups[0]
        expected = importlib.import_module(
            'tests.fixtures.runner.all_pass',
        )
        self.assertIs(module, expected)
        self.assertIsNone(names)

    def test_single_selector_returns_module_with_names(self):
        config = DiscoveryConfig()
        groups = discover_targets(
            ['tests.fixtures.runner.class_simple.Simple.first'],
            config,
        )
        self.assertEqual(len(groups), 1)
        module, names = groups[0]
        expected = importlib.import_module(
            'tests.fixtures.runner.class_simple',
        )
        self.assertIs(module, expected)
        self.assertEqual(names, ['Simple.first'])

    def test_two_distinct_modules(self):
        config = DiscoveryConfig()
        groups = discover_targets(
            [
                'tests.fixtures.runner.all_pass',
                'tests.fixtures.runner.has_failure',
            ],
            config,
        )
        self.assertEqual(len(groups), 2)
        self.assertEqual(
            groups[0][0].__name__,
            'tests.fixtures.runner.all_pass',
        )
        self.assertEqual(
            groups[1][0].__name__,
            'tests.fixtures.runner.has_failure',
        )

    def test_duplicate_module_deduped(self):
        config = DiscoveryConfig()
        groups = discover_targets(
            [
                'tests.fixtures.runner.all_pass',
                'tests.fixtures.runner.all_pass',
            ],
            config,
        )
        self.assertEqual(len(groups), 1)
        _, names = groups[0]
        self.assertIsNone(names)

    def test_module_then_selector_for_same_module_keeps_module(self):
        config = DiscoveryConfig()
        groups = discover_targets(
            [
                'tests.fixtures.runner.all_pass',
                'tests.fixtures.runner.all_pass.passes_one',
            ],
            config,
        )
        self.assertEqual(len(groups), 1)
        _, names = groups[0]
        self.assertIsNone(names)

    def test_two_selectors_same_module_merge_names(self):
        config = DiscoveryConfig()
        groups = discover_targets(
            [
                'tests.fixtures.runner.class_simple.Simple.first',
                'tests.fixtures.runner.class_simple.Simple.second',
            ],
            config,
        )
        self.assertEqual(len(groups), 1)
        _, names = groups[0]
        self.assertEqual(names, ['Simple.first', 'Simple.second'])

    def test_directory_argv_yields_one_entry_per_py_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / 'a.py').write_text(
                'from testsweet import test\n'
                '@test\n'
                'def t():\n'
                '    pass\n'
            )
            (root / 'b.py').write_text(
                'from testsweet import test\n'
                '@test\n'
                'def t():\n'
                '    pass\n'
            )
            config = DiscoveryConfig()
            groups = discover_targets([str(root)], config)
        self.assertEqual(len(groups), 2)
        for _, names in groups:
            self.assertIsNone(names)

    def test_bare_invocation_with_include_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp).resolve()
            sub = root / 'sub'
            sub.mkdir()
            (sub / 'in_sub.py').write_text(
                'from testsweet import test\n'
                '@test\n'
                'def in_sub():\n'
                '    pass\n'
            )
            other = root / 'other'
            other.mkdir()
            (other / 'in_other.py').write_text(
                'from testsweet import test\n'
                '@test\n'
                'def in_other():\n'
                '    pass\n'
            )
            config = DiscoveryConfig(
                include_paths=('sub/**',),
                project_root=root,
            )
            groups = discover_targets([], config)
        names_seen = sorted(
            getattr(module, '__name__', '') for module, _ in groups
        )
        self.assertTrue(
            any('in_sub' in n for n in names_seen),
            msg=f'expected sub/ module; got {names_seen}',
        )
        self.assertFalse(
            any('in_other' in n for n in names_seen),
            msg=f'unexpected other/ module; got {names_seen}',
        )

    def test_bare_invocation_walks_cwd_when_no_include_paths(self):
        # discover_targets reads cwd via pathlib.Path('.').resolve()
        # inside _bare_invocation. contextlib.chdir restores cwd
        # even if the body raises.
        config = DiscoveryConfig()
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp).resolve()
            (root / 'cwd_test.py').write_text(
                'from testsweet import test\n'
                '@test\n'
                'def from_cwd():\n'
                '    pass\n'
            )
            with contextlib.chdir(root):
                groups = discover_targets([], config)
        self.assertEqual(len(groups), 1)
        module, names = groups[0]
        self.assertIsNone(names)
        self.assertTrue(hasattr(module, 'from_cwd'))


if __name__ == '__main__':
    unittest.main()
