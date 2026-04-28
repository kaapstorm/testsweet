import pathlib
import tempfile
import textwrap

from testsweet import (
    ConfigurationError,
    catch_exceptions,
    test,
    test_params,
)
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

    @test_params(
        [
            (
                """
                    [tool.testsweet.discovery]
                    include_paths = "tests/"
                """,
                'include_paths',
            ),
            (
                """
                    [tool.testsweet.discovery]
                    test_files = ["test_*.py", 42]
                """,
                'test_files',
            ),
            (
                """
                    [tool.testsweet.discovery]
                    include_paths = ["tests/**"]
                    typoed_key = ["nope"]
                """,
                'typoed_key',
            ),
        ]
    )
    def invalid_pyproject_raises(self, body, expected_key):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / 'pyproject.toml').write_text(
                textwrap.dedent(body).lstrip()
            )
            with catch_exceptions() as excs:
                load_config(root)
        assert len(excs) == 1
        assert isinstance(excs[0], ConfigurationError)
        assert expected_key in str(excs[0])
