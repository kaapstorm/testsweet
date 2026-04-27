import pathlib
import tempfile
import unittest
import unittest.mock

from assertions._walk import _walk_directory


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
