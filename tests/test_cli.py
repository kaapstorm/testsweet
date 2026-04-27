import subprocess
import sys
import unittest


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

    def test_no_arguments_exits_two(self):
        result = _run_cli()
        self.assertEqual(result.returncode, 2)
        self.assertIn(
            'usage: python -m assertions <target> [<target>...]',
            result.stderr,
        )

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


if __name__ == '__main__':
    unittest.main()
