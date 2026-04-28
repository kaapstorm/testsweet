import pathlib
import tempfile
import textwrap
import unittest

from testsweet import ConfigurationError
from testsweet._config import DiscoveryConfig, load_config


class TestLoadConfig(unittest.TestCase):
    def test_no_pyproject_returns_empty_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = load_config(pathlib.Path(tmp))
        self.assertEqual(config, DiscoveryConfig())
        self.assertIsNone(config.project_root)

    def test_pyproject_without_discovery_section(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / 'pyproject.toml').write_text(
                textwrap.dedent("""
                    [project]
                    name = "demo"
                """).lstrip()
            )
            config = load_config(root)
        self.assertEqual(config.include_paths, ())
        self.assertEqual(config.exclude_paths, ())
        self.assertEqual(config.test_files, ())
        self.assertEqual(config.project_root, root.resolve())

    def test_full_discovery_section(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / 'pyproject.toml').write_text(
                textwrap.dedent("""
                    [tool.testsweet.discovery]
                    include_paths = ["tests/**"]
                    exclude_paths = ["src/vendored/**"]
                    test_files = ["test_*.py", "*_tests.py"]
                """).lstrip()
            )
            config = load_config(root)
        self.assertEqual(config.include_paths, ('tests/**',))
        self.assertEqual(
            config.exclude_paths,
            ('src/vendored/**',),
        )
        self.assertEqual(
            config.test_files,
            ('test_*.py', '*_tests.py'),
        )
        self.assertEqual(config.project_root, root.resolve())

    def test_walks_up_from_subdirectory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / 'pyproject.toml').write_text('[project]\nname = "x"\n')
            sub = root / 'a' / 'b' / 'c'
            sub.mkdir(parents=True)
            config = load_config(sub)
        self.assertEqual(config.project_root, root.resolve())

    def test_non_list_value_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / 'pyproject.toml').write_text(
                textwrap.dedent("""
                    [tool.testsweet.discovery]
                    include_paths = "tests/"
                """).lstrip()
            )
            with self.assertRaises(ConfigurationError) as ctx:
                load_config(root)
        self.assertIn('include_paths', str(ctx.exception))

    def test_list_with_non_string_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / 'pyproject.toml').write_text(
                textwrap.dedent("""
                    [tool.testsweet.discovery]
                    test_files = ["test_*.py", 42]
                """).lstrip()
            )
            with self.assertRaises(ConfigurationError) as ctx:
                load_config(root)
        self.assertIn('test_files', str(ctx.exception))

    def test_unknown_key_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / 'pyproject.toml').write_text(
                textwrap.dedent("""
                    [tool.testsweet.discovery]
                    include_paths = ["tests/**"]
                    typoed_key = ["nope"]
                """).lstrip()
            )
            with self.assertRaises(ConfigurationError) as ctx:
                load_config(root)
        self.assertIn('typoed_key', str(ctx.exception))


if __name__ == '__main__':
    unittest.main()
