import pathlib
import subprocess
import sys
import unittest


_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, '-m', 'assertions', *args],
        capture_output=True,
        text=True,
    )


class TestCli(unittest.TestCase):
    def test_all_pass_module_exits_zero(self):
        result = _run_cli('tests.fixtures.runner.all_pass')
        self.assertEqual(result.returncode, 0)
        self.assertIn('passes_one ... ok', result.stdout)
        self.assertIn('passes_two ... ok', result.stdout)

    def test_failing_module_exits_one(self):
        result = _run_cli('tests.fixtures.runner.has_failure')
        self.assertEqual(result.returncode, 1)
        self.assertIn('passes ... ok', result.stdout)
        self.assertIn('fails ... FAIL:', result.stdout)
        self.assertIn('AssertionError', result.stdout)

    def test_two_arguments_exits_two(self):
        result = _run_cli('a', 'b')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('ModuleNotFoundError', result.stderr)

    def test_unimportable_module_propagates(self):
        result = _run_cli('not_a_real_module_xyzzy')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('ModuleNotFoundError', result.stderr)

    def test_class_method_qualname_in_output(self):
        result = _run_cli('tests.fixtures.runner.class_simple')
        self.assertEqual(result.returncode, 0)
        self.assertIn('Simple.first ... ok', result.stdout)
        self.assertIn('Simple.second ... ok', result.stdout)

    def test_parameterized_indices_in_output(self):
        result = _run_cli('tests.fixtures.runner.params_simple')
        self.assertEqual(result.returncode, 0)
        self.assertIn('adds[0] ... ok', result.stdout)
        self.assertIn('adds[1] ... ok', result.stdout)

    def test_file_path_argv(self):
        result = _run_cli('tests/fixtures/runner/all_pass.py')
        self.assertEqual(result.returncode, 0)
        self.assertIn('passes_one ... ok', result.stdout)
        self.assertIn('passes_two ... ok', result.stdout)

    def test_selector_argv_runs_one_method(self):
        result = _run_cli(
            'tests.fixtures.runner.class_simple.Simple.first',
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn('Simple.first ... ok', result.stdout)
        self.assertNotIn('Simple.second', result.stdout)

    def test_two_module_targets(self):
        result = _run_cli(
            'tests.fixtures.runner.all_pass',
            'tests.fixtures.runner.has_failure',
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn('passes_one ... ok', result.stdout)
        self.assertIn('fails ... FAIL:', result.stdout)

    def test_two_selectors_same_module_grouped(self):
        result = _run_cli(
            'tests.fixtures.runner.class_simple.Simple.first',
            'tests.fixtures.runner.class_simple.Simple.second',
        )
        self.assertEqual(result.returncode, 0)
        # Both methods, single grouped run — neither line repeats.
        self.assertEqual(result.stdout.count('Simple.first ... ok'), 1)
        self.assertEqual(
            result.stdout.count('Simple.second ... ok'),
            1,
        )

    def test_unmatched_selector_propagates_lookup_error(self):
        result = _run_cli(
            'tests.fixtures.runner.all_pass.nonexistent',
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('LookupError', result.stderr)

    def test_module_target_overrides_selector_for_same_module(self):
        result = _run_cli(
            'tests.fixtures.runner.all_pass',
            'tests.fixtures.runner.all_pass.passes_one',
        )
        self.assertEqual(result.returncode, 0)
        # Whole-module form wins; both functions run.
        self.assertIn('passes_one ... ok', result.stdout)
        self.assertIn('passes_two ... ok', result.stdout)

    def test_bare_invocation_walks_cwd(self):
        import tempfile
        import textwrap

        with tempfile.TemporaryDirectory() as tmp:
            (pathlib.Path(tmp) / 'test_simple.py').write_text(
                textwrap.dedent("""
                    from assertions import test

                    @test
                    def passes():
                        assert True
                """).lstrip()
            )
            result = subprocess.run(
                [sys.executable, '-m', 'assertions'],
                capture_output=True,
                text=True,
                cwd=tmp,
            )
        self.assertEqual(result.returncode, 0)
        self.assertIn('passes ... ok', result.stdout)

    def test_directory_argument_walks_recursively(self):
        import tempfile
        import textwrap

        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / 'test_a.py').write_text(
                textwrap.dedent("""
                    from assertions import test

                    @test
                    def passes_a():
                        assert True
                """).lstrip()
            )
            sub = root / 'sub'
            sub.mkdir()
            (sub / 'test_b.py').write_text(
                textwrap.dedent("""
                    from assertions import test

                    @test
                    def passes_b():
                        assert True
                """).lstrip()
            )
            result = subprocess.run(
                [sys.executable, '-m', 'assertions', tmp],
                capture_output=True,
                text=True,
                cwd=_REPO_ROOT,
            )
        self.assertEqual(result.returncode, 0)
        self.assertIn('passes_a ... ok', result.stdout)
        self.assertIn('passes_b ... ok', result.stdout)

    def test_walked_file_with_import_error_propagates(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            (pathlib.Path(tmp) / 'broken.py').write_text(
                'import this_does_not_exist_assertions_test\n'
            )
            result = subprocess.run(
                [sys.executable, '-m', 'assertions', tmp],
                capture_output=True,
                text=True,
                cwd=_REPO_ROOT,
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('ModuleNotFoundError', result.stderr)

    def test_sys_path_is_restored_after_main(self):
        import importlib
        import tempfile
        import textwrap

        from assertions import __main__ as cli_main

        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            pkg = root / 'walkpkg'
            pkg.mkdir()
            (pkg / '__init__.py').write_text('')
            (pkg / 'test_inside.py').write_text(
                textwrap.dedent("""
                    from assertions import test

                    @test
                    def passes():
                        assert True
                """).lstrip()
            )
            saved = list(sys.path)
            try:
                cli_main.main([str(root)])
            finally:
                # main should restore sys.path even if it raises.
                pass
            self.assertEqual(sys.path, saved)
            # Reload to clean up sys.modules pollution from the test.
            for name in list(sys.modules):
                if name == 'walkpkg' or name.startswith('walkpkg.'):
                    del sys.modules[name]


if __name__ == '__main__':
    unittest.main()
