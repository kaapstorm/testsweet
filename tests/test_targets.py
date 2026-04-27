import importlib
import os
import pathlib
import tempfile
import unittest

from assertions._loaders import _dotted_name_for_path
from assertions._targets import parse_target
from assertions._walk import _walk_directory


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


class TestWalkDirectory(unittest.TestCase):
    def test_returns_py_files_alphabetical(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / 'b.py').write_text('')
            (root / 'a.py').write_text('')
            (root / 'c.py').write_text('')
            paths = _walk_directory(root)
            self.assertEqual(
                [p.name for p in paths],
                ['a.py', 'b.py', 'c.py'],
            )

    def test_recurses_subdirectories(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / 'top.py').write_text('')
            sub = root / 'sub'
            sub.mkdir()
            (sub / 'inner.py').write_text('')
            paths = _walk_directory(root)
            names = [p.relative_to(root).as_posix() for p in paths]
            self.assertEqual(names, ['sub/inner.py', 'top.py'])

    def test_excludes_hidden_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / 'visible.py').write_text('')
            hidden = root / '.hidden'
            hidden.mkdir()
            (hidden / 'inside.py').write_text('')
            paths = _walk_directory(root)
            self.assertEqual(
                [p.name for p in paths],
                ['visible.py'],
            )

    def test_excludes_pycache(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / 'visible.py').write_text('')
            cache = root / '__pycache__'
            cache.mkdir()
            (cache / 'inside.py').write_text('')
            paths = _walk_directory(root)
            self.assertEqual(
                [p.name for p in paths],
                ['visible.py'],
            )

    def test_excludes_node_modules(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / 'visible.py').write_text('')
            nm = root / 'node_modules'
            nm.mkdir()
            (nm / 'inside.py').write_text('')
            paths = _walk_directory(root)
            self.assertEqual(
                [p.name for p in paths],
                ['visible.py'],
            )

    def test_empty_when_no_py_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = _walk_directory(pathlib.Path(tmp))
            self.assertEqual(paths, [])


class TestDottedNameForPath(unittest.TestCase):
    def test_returns_dotted_name_for_packaged_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            pkg = root / 'pkg'
            pkg.mkdir()
            (pkg / '__init__.py').write_text('')
            sub = pkg / 'sub'
            sub.mkdir()
            (sub / '__init__.py').write_text('')
            target = sub / 'mod.py'
            target.write_text('')
            dotted, rootdir = _dotted_name_for_path(target)
            self.assertEqual(dotted, 'pkg.sub.mod')
            self.assertEqual(rootdir, root)

    def test_returns_none_for_loose_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            target = root / 'loose.py'
            target.write_text('')
            dotted, rootdir = _dotted_name_for_path(target)
            self.assertIsNone(dotted)
            self.assertIsNone(rootdir)

    def test_top_level_package_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            pkg = root / 'pkg'
            pkg.mkdir()
            (pkg / '__init__.py').write_text('')
            target = pkg / 'mod.py'
            target.write_text('')
            dotted, rootdir = _dotted_name_for_path(target)
            self.assertEqual(dotted, 'pkg.mod')
            self.assertEqual(rootdir, root)


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


class TestExecModuleFromPath(unittest.TestCase):
    def test_loads_a_simple_module(self):
        from assertions._loaders import _exec_module_from_path

        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / 'demo.py'
            path.write_text('value = 42\n')
            module = _exec_module_from_path(path)
        self.assertEqual(getattr(module, 'value'), 42)
        self.assertEqual(module.__name__, 'demo')

    def test_unloadable_path_raises_import_error(self):
        from assertions._loaders import _exec_module_from_path

        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / 'missing.py'
            with self.assertRaises((ImportError, FileNotFoundError)):
                _exec_module_from_path(path)


class TestWalkDirectoryWithConfig(unittest.TestCase):
    def test_test_files_filter_keeps_matching_names(self):
        from assertions._config import DiscoveryConfig
        from assertions._walk import _walk_directory

        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / 'test_a.py').write_text('')
            (root / 'b_tests.py').write_text('')
            (root / 'helper.py').write_text('')
            config = DiscoveryConfig(
                test_files=('test_*.py', '*_tests.py'),
            )
            paths = _walk_directory(root, config=config, excluded=set())
        self.assertEqual(
            sorted(p.name for p in paths),
            ['b_tests.py', 'test_a.py'],
        )

    def test_test_files_filter_with_no_match(self):
        from assertions._config import DiscoveryConfig
        from assertions._walk import _walk_directory

        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / 'helper.py').write_text('')
            config = DiscoveryConfig(test_files=('test_*.py',))
            paths = _walk_directory(root, config=config, excluded=set())
        self.assertEqual(paths, [])

    def test_excluded_set_drops_files(self):
        from assertions._config import DiscoveryConfig
        from assertions._walk import _walk_directory

        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            keep = root / 'keep.py'
            drop = root / 'drop.py'
            keep.write_text('')
            drop.write_text('')
            paths = _walk_directory(
                root,
                config=DiscoveryConfig(),
                excluded={drop.resolve()},
            )
        self.assertEqual(
            [p.name for p in paths],
            ['keep.py'],
        )

    def test_default_args_preserve_old_behavior(self):
        from assertions._walk import _walk_directory

        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / 'a.py').write_text('')
            (root / 'b.py').write_text('')
            paths_no_args = _walk_directory(root)
        self.assertEqual(
            sorted(p.name for p in paths_no_args),
            ['a.py', 'b.py'],
        )

    def test_filters_apply_with_excluded(self):
        from assertions._config import DiscoveryConfig
        from assertions._walk import _walk_directory

        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / 'test_a.py').write_text('')
            test_b = root / 'test_b.py'
            test_b.write_text('')
            config = DiscoveryConfig(test_files=('test_*.py',))
            paths = _walk_directory(
                root,
                config=config,
                excluded={test_b.resolve()},
            )
        self.assertEqual(
            [p.name for p in paths],
            ['test_a.py'],
        )


if __name__ == '__main__':
    unittest.main()
