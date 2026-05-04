import pathlib
import tempfile

from testsweet import params, test
from testsweet._config import DiscoveryConfig
from testsweet._walk import (
    _build_exclude_set,
    _resolve_include_paths,
    _walk_directory,
)


@test
class WalkDirectory:
    def returns_py_files_alphabetical(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / 'b.py').write_text('')
            (root / 'a.py').write_text('')
            (root / 'c.py').write_text('')
            paths = _walk_directory(root)
            assert [p.name for p in paths] == ['a.py', 'b.py', 'c.py']

    def recurses_subdirectories(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / 'top.py').write_text('')
            sub = root / 'sub'
            sub.mkdir()
            (sub / 'inner.py').write_text('')
            paths = _walk_directory(root)
            names = [p.relative_to(root).as_posix() for p in paths]
            assert names == ['sub/inner.py', 'top.py']

    @params([('.hidden',), ('__pycache__',), ('node_modules',)])
    def excludes_directory(self, dirname):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / 'visible.py').write_text('')
            excluded = root / dirname
            excluded.mkdir()
            (excluded / 'inside.py').write_text('')
            paths = _walk_directory(root)
            assert [p.name for p in paths] == ['visible.py']

    def empty_when_no_py_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = _walk_directory(pathlib.Path(tmp))
            assert paths == []


@test
class WalkDirectoryWithConfig:
    def test_files_filter_keeps_matching_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / 'test_a.py').write_text('')
            (root / 'b_tests.py').write_text('')
            (root / 'helper.py').write_text('')
            config = DiscoveryConfig(
                test_files=('test_*.py', '*_tests.py'),
            )
            paths = _walk_directory(root, config=config, excluded=set())
        assert sorted(p.name for p in paths) == [
            'b_tests.py',
            'test_a.py',
        ]

    def test_files_filter_with_no_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / 'helper.py').write_text('')
            config = DiscoveryConfig(test_files=('test_*.py',))
            paths = _walk_directory(root, config=config, excluded=set())
        assert paths == []

    def excluded_set_drops_files(self):
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
        assert [p.name for p in paths] == ['keep.py']

    def default_args_preserve_old_behavior(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / 'a.py').write_text('')
            (root / 'b.py').write_text('')
            paths_no_args = _walk_directory(root)
        assert sorted(p.name for p in paths_no_args) == ['a.py', 'b.py']

    def filters_apply_with_excluded(self):
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
        assert [p.name for p in paths] == ['test_a.py']


@test
class GlobContainment:
    def include_paths_outside_project_root_are_dropped(self):
        with tempfile.TemporaryDirectory() as tmp:
            outside = pathlib.Path(tmp).resolve()
            project = outside / 'project'
            project.mkdir()
            (project / 'inside.py').write_text('')
            (outside / 'sibling.py').write_text('')
            config = DiscoveryConfig(
                include_paths=('inside.py', '../sibling.py'),
                project_root=project,
            )
            paths = _resolve_include_paths(config)
        names = [p.name for p in paths]
        assert names == ['inside.py']

    def exclude_paths_outside_project_root_are_dropped(self):
        with tempfile.TemporaryDirectory() as tmp:
            outside = pathlib.Path(tmp).resolve()
            project = outside / 'project'
            project.mkdir()
            (project / 'kept.py').write_text('')
            (outside / 'other.py').write_text('')
            config = DiscoveryConfig(
                exclude_paths=('kept.py', '../other.py'),
                project_root=project,
            )
            excluded = _build_exclude_set(config)
        names = {p.name for p in excluded}
        assert names == {'kept.py'}
