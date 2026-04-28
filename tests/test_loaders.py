import pathlib
import tempfile
import unittest

from testsweet._loaders import _dotted_name_for_path


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
            info = _dotted_name_for_path(target)
            self.assertIsNotNone(info)
            assert info is not None  # narrow for mypy
            dotted, rootdir = info
            self.assertEqual(dotted, 'pkg.sub.mod')
            self.assertEqual(rootdir, root)

    def test_returns_none_for_loose_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            target = root / 'loose.py'
            target.write_text('')
            self.assertIsNone(_dotted_name_for_path(target))

    def test_top_level_package_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            pkg = root / 'pkg'
            pkg.mkdir()
            (pkg / '__init__.py').write_text('')
            target = pkg / 'mod.py'
            target.write_text('')
            info = _dotted_name_for_path(target)
            self.assertIsNotNone(info)
            assert info is not None
            dotted, rootdir = info
            self.assertEqual(dotted, 'pkg.mod')
            self.assertEqual(rootdir, root)


class TestExecModuleFromPath(unittest.TestCase):
    def test_loads_a_simple_module(self):
        from testsweet._loaders import _exec_module_from_path

        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / 'demo.py'
            path.write_text('value = 42\n')
            module = _exec_module_from_path(path)
        self.assertEqual(getattr(module, 'value'), 42)
        self.assertEqual(module.__name__, 'demo')

    def test_unloadable_path_raises_import_error(self):
        from testsweet._loaders import _exec_module_from_path

        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / 'missing.py'
            with self.assertRaises((ImportError, FileNotFoundError)):
                _exec_module_from_path(path)


if __name__ == '__main__':
    unittest.main()
