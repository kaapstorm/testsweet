import pathlib
import subprocess
import sys
import tempfile
import textwrap

from testsweet import test, test_params


_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, '-m', 'testsweet', *args],
        capture_output=True,
        text=True,
    )


@test
class Cli:
    def _make_test_module(self, root, name, body):
        (root / name).write_text(textwrap.dedent(body).lstrip())

    def _passing_test(self, func_name='passes'):
        return f"""
            from testsweet import test

            @test
            def {func_name}():
                assert True
        """

    @test_params(
        [
            (
                ('tests.fixtures.runner.all_pass',),
                ['passes_one ... ok', 'passes_two ... ok'],
            ),
            (
                ('tests.fixtures.runner.class_simple',),
                ['Simple.first ... ok', 'Simple.second ... ok'],
            ),
            (
                ('tests.fixtures.runner.params_simple',),
                ['adds[0] ... ok', 'adds[1] ... ok'],
            ),
            (
                ('tests/fixtures/runner/all_pass.py',),
                ['passes_one ... ok', 'passes_two ... ok'],
            ),
        ]
    )
    def runs_target_with_expected_lines(self, args, expected_lines):
        result = _run_cli(*args)
        assert result.returncode == 0
        for line in expected_lines:
            assert line in result.stdout

    def failing_module_exits_one(self):
        result = _run_cli('tests.fixtures.runner.has_failure')
        assert result.returncode == 1
        assert 'passes ... ok' in result.stdout
        assert 'fails ... FAIL:' in result.stdout
        assert 'AssertionError' in result.stdout

    @test_params(
        [
            (('a', 'b'), 'ModuleNotFoundError'),
            (('not_a_real_module_xyzzy',), 'ModuleNotFoundError'),
            (
                ('tests.fixtures.runner.all_pass.nonexistent',),
                'LookupError',
            ),
        ]
    )
    def invalid_target_writes_to_stderr(self, args, expected_substring):
        result = _run_cli(*args)
        assert result.returncode != 0
        assert expected_substring in result.stderr

    def selector_argv_runs_one_method(self):
        result = _run_cli(
            'tests.fixtures.runner.class_simple.Simple.first',
        )
        assert result.returncode == 0
        assert 'Simple.first ... ok' in result.stdout
        assert 'Simple.second' not in result.stdout

    def two_module_targets(self):
        result = _run_cli(
            'tests.fixtures.runner.all_pass',
            'tests.fixtures.runner.has_failure',
        )
        assert result.returncode == 1
        assert 'passes_one ... ok' in result.stdout
        assert 'fails ... FAIL:' in result.stdout

    def two_selectors_same_module_grouped(self):
        result = _run_cli(
            'tests.fixtures.runner.class_simple.Simple.first',
            'tests.fixtures.runner.class_simple.Simple.second',
        )
        assert result.returncode == 0
        # Both methods, single grouped run — neither line repeats.
        assert result.stdout.count('Simple.first ... ok') == 1
        assert result.stdout.count('Simple.second ... ok') == 1

    def module_target_overrides_selector_for_same_module(self):
        result = _run_cli(
            'tests.fixtures.runner.all_pass',
            'tests.fixtures.runner.all_pass.passes_one',
        )
        assert result.returncode == 0
        # Whole-module form wins; both functions run.
        assert 'passes_one ... ok' in result.stdout
        assert 'passes_two ... ok' in result.stdout

    def bare_invocation_walks_cwd(self):
        with tempfile.TemporaryDirectory() as tmp:
            (pathlib.Path(tmp) / 'test_simple.py').write_text(
                textwrap.dedent("""
                    from testsweet import test

                    @test
                    def passes():
                        assert True
                """).lstrip()
            )
            result = subprocess.run(
                [sys.executable, '-m', 'testsweet'],
                capture_output=True,
                text=True,
                cwd=tmp,
            )
        assert result.returncode == 0
        assert 'passes ... ok' in result.stdout

    def directory_argument_walks_recursively(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / 'test_a.py').write_text(
                textwrap.dedent("""
                    from testsweet import test

                    @test
                    def passes_a():
                        assert True
                """).lstrip()
            )
            sub = root / 'sub'
            sub.mkdir()
            (sub / 'test_b.py').write_text(
                textwrap.dedent("""
                    from testsweet import test

                    @test
                    def passes_b():
                        assert True
                """).lstrip()
            )
            result = subprocess.run(
                [sys.executable, '-m', 'testsweet', tmp],
                capture_output=True,
                text=True,
                cwd=_REPO_ROOT,
            )
        assert result.returncode == 0
        assert 'passes_a ... ok' in result.stdout
        assert 'passes_b ... ok' in result.stdout

    def walked_file_with_import_error_propagates(self):
        with tempfile.TemporaryDirectory() as tmp:
            (pathlib.Path(tmp) / 'broken.py').write_text(
                'import this_does_not_exist_testsweet_test\n'
            )
            result = subprocess.run(
                [sys.executable, '-m', 'testsweet', tmp],
                capture_output=True,
                text=True,
                cwd=_REPO_ROOT,
            )
        assert result.returncode != 0
        assert 'ModuleNotFoundError' in result.stderr

    def sys_path_is_restored_after_main(self):
        from testsweet import __main__ as cli_main

        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            pkg = root / 'walkpkg'
            pkg.mkdir()
            (pkg / '__init__.py').write_text('')
            (pkg / 'test_inside.py').write_text(
                textwrap.dedent("""
                    from testsweet import test

                    @test
                    def passes():
                        assert True
                """).lstrip()
            )
            saved = list(sys.path)
            cli_main.main([str(root)])
            assert sys.path == saved
            # Reload to clean up sys.modules pollution from the test.
            for name in list(sys.modules):
                if name == 'walkpkg' or name.startswith('walkpkg.'):
                    del sys.modules[name]

    def config_include_paths_narrows_walk(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            sub = root / 'sub'
            sub.mkdir()
            other = root / 'other'
            other.mkdir()
            self._make_test_module(
                sub,
                'test_in_sub.py',
                self._passing_test('in_sub'),
            )
            self._make_test_module(
                other,
                'test_in_other.py',
                self._passing_test('in_other'),
            )
            (root / 'pyproject.toml').write_text(
                '[tool.testsweet.discovery]\n'
                'include_paths = ["sub/**"]\n'
            )
            result = subprocess.run(
                [sys.executable, '-m', 'testsweet'],
                capture_output=True,
                text=True,
                cwd=tmp,
            )
        assert result.returncode == 0
        assert 'in_sub ... ok' in result.stdout
        assert 'in_other' not in result.stdout

    def config_exclude_paths_drops_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            self._make_test_module(
                root,
                'test_keep.py',
                self._passing_test('keep'),
            )
            vendored = root / 'vendored'
            vendored.mkdir()
            self._make_test_module(
                vendored,
                'test_drop.py',
                self._passing_test('drop'),
            )
            (root / 'pyproject.toml').write_text(
                '[tool.testsweet.discovery]\n'
                'exclude_paths = ["vendored/**"]\n'
            )
            result = subprocess.run(
                [sys.executable, '-m', 'testsweet'],
                capture_output=True,
                text=True,
                cwd=tmp,
            )
        assert result.returncode == 0
        assert 'keep ... ok' in result.stdout
        assert 'drop' not in result.stdout

    def config_test_files_filters_filenames(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            self._make_test_module(
                root,
                'test_match.py',
                self._passing_test('matched'),
            )
            self._make_test_module(
                root,
                'helper.py',
                self._passing_test('skipped'),
            )
            (root / 'pyproject.toml').write_text(
                '[tool.testsweet.discovery]\n'
                'test_files = ["test_*.py"]\n'
            )
            result = subprocess.run(
                [sys.executable, '-m', 'testsweet'],
                capture_output=True,
                text=True,
                cwd=tmp,
            )
        assert result.returncode == 0
        assert 'matched ... ok' in result.stdout
        assert 'skipped' not in result.stdout

    def argv_directory_ignores_include_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            sub = root / 'sub'
            sub.mkdir()
            other = root / 'other'
            other.mkdir()
            self._make_test_module(
                sub,
                'test_in_sub.py',
                self._passing_test('in_sub'),
            )
            self._make_test_module(
                other,
                'test_in_other.py',
                self._passing_test('in_other'),
            )
            (root / 'pyproject.toml').write_text(
                '[tool.testsweet.discovery]\n'
                'include_paths = ["sub/**"]\n'
            )
            result = subprocess.run(
                [sys.executable, '-m', 'testsweet', 'other'],
                capture_output=True,
                text=True,
                cwd=tmp,
            )
        assert result.returncode == 0
        assert 'in_other ... ok' in result.stdout
        assert 'in_sub' not in result.stdout

    def argv_directory_still_honors_exclude_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            src = root / 'src'
            src.mkdir()
            self._make_test_module(
                src,
                'test_keep.py',
                self._passing_test('keep'),
            )
            vendored = src / 'vendored'
            vendored.mkdir()
            self._make_test_module(
                vendored,
                'test_drop.py',
                self._passing_test('drop'),
            )
            (root / 'pyproject.toml').write_text(
                '[tool.testsweet.discovery]\n'
                'exclude_paths = ["src/vendored/**"]\n'
            )
            result = subprocess.run(
                [sys.executable, '-m', 'testsweet', 'src'],
                capture_output=True,
                text=True,
                cwd=tmp,
            )
        assert result.returncode == 0
        assert 'keep ... ok' in result.stdout
        assert 'drop' not in result.stdout

    def invalid_config_raises_configuration_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            self._make_test_module(
                root,
                'test_a.py',
                self._passing_test('a'),
            )
            (root / 'pyproject.toml').write_text(
                '[tool.testsweet.discovery]\n'
                'typoed_key = ["nope"]\n'
            )
            result = subprocess.run(
                [sys.executable, '-m', 'testsweet'],
                capture_output=True,
                text=True,
                cwd=tmp,
            )
        assert result.returncode != 0
        assert 'ConfigurationError' in result.stderr
        assert 'typoed_key' in result.stderr

    def fail_line_shows_assertion_source_when_no_message(self):
        result = _run_cli(
            'tests.fixtures.runner.assertion_diagnostics.compare_vars',
        )
        assert result.returncode == 1
        assert (
            'FAIL: AssertionError: assert foo == bar' in result.stdout
        )

    def fail_line_keeps_explicit_assertion_message(self):
        result = _run_cli(
            'tests.fixtures.runner.assertion_diagnostics.with_message',
        )
        assert result.returncode == 1
        assert (
            'FAIL: AssertionError: explicit message' in result.stdout
        )
        assert 'assert 1 == 2' not in result.stdout.split('\n')[0]

    def traceback_block_shows_subexpression_values(self):
        result = _run_cli(
            'tests.fixtures.runner.assertion_diagnostics.compare_vars',
        )
        assert 'foo = 1' in result.stdout
        assert 'bar = 0' in result.stdout

    def traceback_block_explains_bare_name_assertion(self):
        result = _run_cli(
            'tests.fixtures.runner.assertion_diagnostics.bare_name',
        )
        assert 'flag = False' in result.stdout

    def traceback_block_explains_bool_op_assertion(self):
        result = _run_cli(
            'tests.fixtures.runner.assertion_diagnostics.bool_op',
        )
        assert 'a > b = False' in result.stdout
        assert 'b > 0 = True' in result.stdout

    def non_assertion_error_has_no_explanation_block(self):
        result = _run_cli('tests.fixtures.runner.non_assertion_error')
        assert result.returncode == 1
        assert result.stdout.splitlines()[-1] == 'ValueError: boom'
