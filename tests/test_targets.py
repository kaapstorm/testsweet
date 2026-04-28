import contextlib
import importlib
import pathlib
import sys
import tempfile

from testsweet import catch_exceptions, test
from testsweet._config import DiscoveryConfig
from testsweet._targets import discover_targets, parse_target


_FIXTURES = pathlib.Path(__file__).resolve().parent / 'fixtures' / 'runner'


@test
class ParseTarget:
    def dotted_module_no_selector(self):
        result = parse_target('tests.fixtures.runner.all_pass')
        assert len(result) == 1
        module, names = result[0]
        expected = importlib.import_module(
            'tests.fixtures.runner.all_pass',
        )
        assert module is expected
        assert names is None

    def relative_file_path(self):
        result = parse_target('tests/fixtures/runner/all_pass.py')
        assert len(result) == 1
        module, names = result[0]
        assert names is None
        assert hasattr(module, 'passes_one')
        assert hasattr(module, 'passes_two')

    def relative_file_path_with_dot(self):
        result = parse_target('./tests/fixtures/runner/all_pass.py')
        assert len(result) == 1
        module, names = result[0]
        assert names is None
        assert hasattr(module, 'passes_one')

    def absolute_file_path(self):
        path = (_FIXTURES / 'all_pass.py').resolve()
        result = parse_target(str(path))
        assert len(result) == 1
        module, names = result[0]
        assert names is None
        assert hasattr(module, 'passes_one')

    def dotted_selector_one_segment(self):
        result = parse_target(
            'tests.fixtures.runner.all_pass.passes_one',
        )
        assert len(result) == 1
        module, names = result[0]
        expected = importlib.import_module(
            'tests.fixtures.runner.all_pass',
        )
        assert module is expected
        assert names == ['passes_one']

    def dotted_selector_class_only(self):
        result = parse_target(
            'tests.fixtures.runner.class_simple.Simple',
        )
        assert len(result) == 1
        module, names = result[0]
        expected = importlib.import_module(
            'tests.fixtures.runner.class_simple',
        )
        assert module is expected
        assert names == ['Simple']

    def dotted_selector_class_method(self):
        result = parse_target(
            'tests.fixtures.runner.class_simple.Simple.first',
        )
        assert len(result) == 1
        module, names = result[0]
        expected = importlib.import_module(
            'tests.fixtures.runner.class_simple',
        )
        assert module is expected
        assert names == ['Simple.first']

    def dotted_too_many_segments(self):
        with catch_exceptions() as excs:
            parse_target(
                'tests.fixtures.runner.class_simple.Simple.first.extra',
            )
        assert len(excs) == 1
        assert isinstance(excs[0], LookupError)

    def dotted_no_importable_prefix(self):
        with catch_exceptions() as excs:
            parse_target('totally.not.a.module')
        assert len(excs) == 1
        assert isinstance(excs[0], ModuleNotFoundError)

    def internal_import_error_propagates(self):
        with catch_exceptions() as excs:
            parse_target('tests.fixtures.runner.has_broken_import')
        assert len(excs) == 1
        assert isinstance(excs[0], ModuleNotFoundError)
        assert excs[0].name == 'this_dependency_does_not_exist'


# parse_target on a directory imports each discovered .py file,
# which adds entries to sys.modules. Snapshot and restore so
# short-lived tmp-dir module names (`a`, `b`, etc.) don't leak
# between tests and shadow each other on subsequent runs.
@test
class ParseTargetDirectory:
    def __enter__(self):
        self._saved_modules = dict(sys.modules)
        return self

    def __exit__(self, exc_type, exc, tb):
        for name in list(sys.modules):
            if name not in self._saved_modules:
                del sys.modules[name]
        return None

    def directory_yields_one_entry_per_py_file(self):
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
            assert len(result) == 2
            for module, names in result:
                assert names is None

    def nonexistent_directory_raises(self):
        with catch_exceptions() as excs:
            parse_target('/this/path/really/should/not/exist/abc/')
        assert len(excs) == 1
        assert isinstance(excs[0], (FileNotFoundError, ImportError))

    def empty_directory_returns_empty_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = parse_target(str(pathlib.Path(tmp)))
            assert result == []


# discover_targets imports test modules from temp directories, which
# leaves entries in sys.modules. Snapshot/restore so short-lived
# tmp-dir module names don't leak between tests.
@test
class DiscoverTargets:
    def __enter__(self):
        self._saved_modules = dict(sys.modules)
        return self

    def __exit__(self, exc_type, exc, tb):
        for name in list(sys.modules):
            if name not in self._saved_modules:
                del sys.modules[name]
        return None

    def single_dotted_module(self):
        config = DiscoveryConfig()
        groups = discover_targets(
            ['tests.fixtures.runner.all_pass'],
            config,
        )
        assert len(groups) == 1
        module, names = groups[0]
        expected = importlib.import_module(
            'tests.fixtures.runner.all_pass',
        )
        assert module is expected
        assert names is None

    def single_selector_returns_module_with_names(self):
        config = DiscoveryConfig()
        groups = discover_targets(
            ['tests.fixtures.runner.class_simple.Simple.first'],
            config,
        )
        assert len(groups) == 1
        module, names = groups[0]
        expected = importlib.import_module(
            'tests.fixtures.runner.class_simple',
        )
        assert module is expected
        assert names == ['Simple.first']

    def two_distinct_modules(self):
        config = DiscoveryConfig()
        groups = discover_targets(
            [
                'tests.fixtures.runner.all_pass',
                'tests.fixtures.runner.has_failure',
            ],
            config,
        )
        assert len(groups) == 2
        assert groups[0][0].__name__ == 'tests.fixtures.runner.all_pass'
        assert (
            groups[1][0].__name__ == 'tests.fixtures.runner.has_failure'
        )

    def duplicate_module_deduped(self):
        config = DiscoveryConfig()
        groups = discover_targets(
            [
                'tests.fixtures.runner.all_pass',
                'tests.fixtures.runner.all_pass',
            ],
            config,
        )
        assert len(groups) == 1
        _, names = groups[0]
        assert names is None

    def module_then_selector_for_same_module_keeps_module(self):
        config = DiscoveryConfig()
        groups = discover_targets(
            [
                'tests.fixtures.runner.all_pass',
                'tests.fixtures.runner.all_pass.passes_one',
            ],
            config,
        )
        assert len(groups) == 1
        _, names = groups[0]
        assert names is None

    def two_selectors_same_module_merge_names(self):
        config = DiscoveryConfig()
        groups = discover_targets(
            [
                'tests.fixtures.runner.class_simple.Simple.first',
                'tests.fixtures.runner.class_simple.Simple.second',
            ],
            config,
        )
        assert len(groups) == 1
        _, names = groups[0]
        assert names == ['Simple.first', 'Simple.second']

    def directory_argv_yields_one_entry_per_py_file(self):
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
        assert len(groups) == 2
        for _, names in groups:
            assert names is None

    def bare_invocation_with_include_paths(self):
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
        assert any('in_sub' in n for n in names_seen), (
            f'expected sub/ module; got {names_seen}'
        )
        assert not any('in_other' in n for n in names_seen), (
            f'unexpected other/ module; got {names_seen}'
        )

    def bare_invocation_walks_cwd_when_no_include_paths(self):
        # discover_targets reads cwd via pathlib.Path('.').resolve()
        # inside _bare_invocation. contextlib.chdir restores cwd even
        # if the body raises.
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
        assert len(groups) == 1
        module, names = groups[0]
        assert names is None
        assert hasattr(module, 'from_cwd')
