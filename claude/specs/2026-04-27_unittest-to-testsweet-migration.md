# Migrate the test suite from unittest to testsweet

Date: 2026-04-27
Branch (proposed): `nh/migrate-tests`

## Motivation

Testsweet's own test suite is written against `unittest`. Self-hosting
the suite on testsweet is a useful invariant: any regression that
breaks discovery, the runner, or the public API surfaces the moment
the suite stops being runnable. It also exercises the library against
a real, non-trivial codebase.


## Scope

The migration covers everything under `tests/`. Fixture modules in
`tests/fixtures/` are already plain Python and need no changes.


## Audit results

### Keep, port directly (public API coverage)

| File              | Notes                                                    |
|-------------------|----------------------------------------------------------|
| `test_markers.py` | `@test` decorator behavior; small, clean.                |
| `test_catches.py` | `catch_exceptions` / `catch_warnings`; small, clean.     |
| `test_params.py`  | `@test_params` / `@test_params_lazy`; small, clean.      |
| `test_discover.py`| `discover()` over fixture modules.                       |
| `test_config.py`  | `load_config` and `ConfigurationError`; uses tempfiles.  |

### Keep, port (internal logic worth direct coverage)

| File              | Why keep                                                  |
|-------------------|-----------------------------------------------------------|
| `test_walk.py`    | Directory traversal has real branching (include/exclude). |
| `test_targets.py` | Target-parsing grammar (path vs dotted vs `mod::Class.m`).|
| `test_resolve.py` | Selector + parametrization expansion has its own contract.|

These exercise modules whose edge cases are hard to reach reliably
through the public API. Driving every branch through `run()` or the
CLI requires fixture gymnastics that obscure intent.

### Fold

- `test_class_helpers.py` → merge into `test_runner.py`. Most of
  `_public_methods` is already exercised by class-based runner tests;
  only the inheritance/MRO contract tests need to move.

### Drop

- `test_loaders.py` — `_loaders` is a thin wrapper around
  `importlib`; covered indirectly by every other suite.

### Keep separated (don't merge)

- `test_runner.py` — in-process unit tests of `run()`.
- `test_cli.py` — subprocess integration tests of `python -m
  testsweet`.

These are different layers; merging conflates speed/scope.

### Net effect

13 files → 9 files. ~2400 lines → ~1900 lines (estimate).


## Translation rules

The migration is mostly mechanical. The translations:

| unittest                              | testsweet                                                |
|---------------------------------------|----------------------------------------------------------|
| `class Foo(TestCase):`                | `@test\nclass Foo:`                                      |
| `def test_bar(self):`                 | `def bar(self):`  *(public method, no `test_` prefix)*   |
| `def setUp(self):`                    | `def __enter__(self):` *(class becomes a context mgr)*   |
| `def tearDown(self):`                 | `def __exit__(self, exc_type, exc, tb):`                 |
| `self.assertEqual(a, b)`              | `assert a == b`                                          |
| `self.assertIs(a, b)`                 | `assert a is b`                                          |
| `self.assertIn(a, b)`                 | `assert a in b`                                          |
| `self.assertIsNone(a)`                | `assert a is None`                                       |
| `with self.assertRaises(E):`          | `with catch_exceptions() as excs: ...; assert isinstance(excs[0], E)` |
| `self.subTest(x=...)` loop            | `@test_params([...])` on an extracted helper             |
| `unittest.mock.patch(...)`            | Keep as-is; `unittest.mock` is independent of the runner.|

Class-style tests that previously relied on `setUp`/`tearDown` for
shared state become context managers (`AbstractContextManager`
recommended, not required — the runner duck-types).

Underscore-prefixed methods are skipped by testsweet, so any helper
methods on a `TestCase` keep working when they already start with
`_`. Helpers that don't will need a leading underscore.


## Dual-runnability and the unittest shim

The user requirement: both `python -m unittest` and `python -m
testsweet` continue to work after migration.

### Approach

- **Primary runner: testsweet.** All ported tests are written as
  `@test` functions/classes and live in their existing modules.
- **Shim: a single `unittest.TestCase`** at
  `tests/test_unittest_shim.py` that imports the `testsweet` package
  and asserts the public API symbols are present. This keeps `python
  -m unittest discover` exiting zero on a healthy tree without
  duplicating coverage.

Example shim:

```python
import unittest


class ImportSmoke(unittest.TestCase):
    def test_public_api_importable(self):
        import testsweet

        for name in (
            'ConfigurationError',
            'catch_exceptions',
            'catch_warnings',
            'discover',
            'run',
            'test',
            'test_params',
            'test_params_lazy',
        ):
            self.assertTrue(hasattr(testsweet, name), name)
```

### Why a smoke shim and not full dual coverage

Mirroring every test as both a `TestCase` and a `@test` function
doubles maintenance and silently rots when one diverges. The shim
buys the property that matters — *if testsweet is broken, you can
still run something* — without paying the duplication cost.

If testsweet's own discovery or runner is broken, `python -m
unittest` still finds the shim, which proves the package at least
imports.


## Migration plan

Sequenced to surface infrastructure problems early.

### Stage 1 — Wire up the test runner against the existing suite

- Add `[tool.testsweet.discovery]` to `pyproject.toml` pointing at
  `tests/`.
- Confirm `python -m testsweet` runs cleanly against the un-migrated
  suite (it should find no tests, since none are `@test`-decorated;
  exit zero).

### Stage 2 — Port leaf tests

In separate commits:

1. `test_markers.py`
2. `test_catches.py`
3. `test_params.py`
4. `test_discover.py`
5. `test_config.py`

After each commit, both `python -m unittest discover` (covers the
not-yet-migrated files) and `python -m testsweet` (covers the
migrated ones) should pass.

### Stage 3 — Port internal-logic tests

6. `test_walk.py`
7. `test_resolve.py`
8. `test_targets.py`

### Stage 4 — Port the runner and CLI tests, fold class_helpers

9. `test_class_helpers.py` → merged into `test_runner.py` in this
   commit; the file is deleted.
10. `test_runner.py`
11. `test_cli.py`

### Stage 5 — Drop and shim

12. Delete `test_loaders.py`.
13. Add `tests/test_unittest_shim.py`.
14. Verify `python -m unittest discover` finds *only* the shim and
    passes.
15. Verify `python -m testsweet` runs the full migrated suite and
    passes.

### Stage 6 — Documentation

16. Update `docs/contributing.md` with both invocations:
    - `uv run python -m testsweet` — full suite.
    - `uv run python -m unittest` — import smoke check.


## Risks and mitigations

| Risk                                                          | Mitigation                                                       |
|---------------------------------------------------------------|------------------------------------------------------------------|
| Bug in testsweet hides test failures during migration.        | Stage 2 ports run under both runners; divergence is detectable.  |
| `assertRaises` translations lose precision (e.g. regex match).| Audit each call; preserve the message check with a plain `assert in`. |
| `setUp`/`tearDown` semantics differ from `__enter__`/`__exit__` (e.g. `tearDown` runs even on setup failure). | Document where this matters. In practice the test suite's tearDowns are sys.modules cleanup — safe to translate. |
| Subprocess-based CLI tests rely on the package being installed.| Already do; `uv sync` installs editable after the build-system PR.|


## Out of scope

- Rewriting fixture modules.
- Adding new test coverage.
- Performance benchmarks comparing the two runners.


## Acceptance criteria

- `uv run python -m testsweet` exits zero and runs every ported test.
- `uv run python -m unittest discover` exits zero, finds the shim,
  reports no other tests.
- No file in `tests/` (other than the shim) inherits from
  `unittest.TestCase`.
- `tests/fixtures/` is unchanged in behavior.
- `docs/contributing.md` documents both invocations.
