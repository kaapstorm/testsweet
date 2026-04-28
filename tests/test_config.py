import pathlib
import tempfile
import textwrap

from testsweet import ConfigurationError, catch_exceptions, test
from testsweet._config import DiscoveryConfig, load_config


@test
class LoadConfig:
    def no_pyproject_returns_empty_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = load_config(pathlib.Path(tmp))
        assert config == DiscoveryConfig()
        assert config.project_root is None

    def pyproject_without_discovery_section(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / 'pyproject.toml').write_text(
                textwrap.dedent("""
                    [project]
                    name = "demo"
                """).lstrip()
            )
            config = load_config(root)
        assert config.include_paths == ()
        assert config.exclude_paths == ()
        assert config.test_files == ()
        assert config.project_root == root.resolve()

    def full_discovery_section(self):
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
        assert config.include_paths == ('tests/**',)
        assert config.exclude_paths == ('src/vendored/**',)
        assert config.test_files == ('test_*.py', '*_tests.py')
        assert config.project_root == root.resolve()

    def walks_up_from_subdirectory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / 'pyproject.toml').write_text(
                '[project]\nname = "x"\n'
            )
            sub = root / 'a' / 'b' / 'c'
            sub.mkdir(parents=True)
            config = load_config(sub)
        assert config.project_root == root.resolve()

    def non_list_value_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / 'pyproject.toml').write_text(
                textwrap.dedent("""
                    [tool.testsweet.discovery]
                    include_paths = "tests/"
                """).lstrip()
            )
            with catch_exceptions() as excs:
                load_config(root)
        assert len(excs) == 1
        assert isinstance(excs[0], ConfigurationError)
        assert 'include_paths' in str(excs[0])

    def list_with_non_string_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / 'pyproject.toml').write_text(
                textwrap.dedent("""
                    [tool.testsweet.discovery]
                    test_files = ["test_*.py", 42]
                """).lstrip()
            )
            with catch_exceptions() as excs:
                load_config(root)
        assert len(excs) == 1
        assert isinstance(excs[0], ConfigurationError)
        assert 'test_files' in str(excs[0])

    def unknown_key_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / 'pyproject.toml').write_text(
                textwrap.dedent("""
                    [tool.testsweet.discovery]
                    include_paths = ["tests/**"]
                    typoed_key = ["nope"]
                """).lstrip()
            )
            with catch_exceptions() as excs:
                load_config(root)
        assert len(excs) == 1
        assert isinstance(excs[0], ConfigurationError)
        assert 'typoed_key' in str(excs[0])
