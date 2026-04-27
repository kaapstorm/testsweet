# Design: split `_targets.py` by responsibility

## Scope

`_targets.py` is currently 207 lines and contains six discrete
responsibilities crammed together:

1. Target string classification + orchestration (`parse_target`).
2. Dotted-name resolution (`_resolve_dotted`).
3. Directory walking + filtering (`_walk_directory`, `_accepts_file`,
   `_is_excluded_dir`).
4. Config-driven include/exclude path expansion
   (`_resolve_include_paths`, `_build_exclude_set`).
5. Module loading from filesystem paths (`_exec_module_from_path`,
   `_load_path`, `_load_path_for_walk`).
6. Package-aware import naming (`_dotted_name_for_path`).

Split into four files so each unit has one clear job.

In scope:

- Move existing functions into new modules. No behavior change.
- Update internal imports across `__main__.py`, `_runner.py` (none),
  test files (`test_targets.py` splits into multiple files matching
  the new module boundaries).
- Keep all existing tests passing without modification beyond import
  updates.

Out of scope:

- The CLI/discovery boundary leak (point #2 from the post-merge
  review) — `__main__.py` will still import five private names from
  the new files. Addressed in a follow-up slice.
- Runner cleanup (point #3).
- API ergonomics (point #4).
- Any test consolidation or coverage changes.

## Approach

Three new private modules under `src/assertions/`:

- `_classify.py` — pure dotted-name resolution.
- `_walk.py` — filesystem walking and config-driven path expansion.
- `_loaders.py` — module loading from filesystem paths.

`_targets.py` keeps the public-internal `parse_target` and becomes
the thin orchestrator that imports from the three new modules.

## File layout after the split

| File | Functions | Imports it needs |
|------|-----------|------------------|
| `src/assertions/_classify.py` | `_resolve_dotted` | `importlib`, `types.ModuleType` |
| `src/assertions/_walk.py` | `_walk_directory`, `_accepts_file`, `_is_excluded_dir`, `_resolve_include_paths`, `_build_exclude_set` | `fnmatch`, `os`, `pathlib`, `assertions._config.DiscoveryConfig` |
| `src/assertions/_loaders.py` | `_exec_module_from_path`, `_load_path`, `_load_path_for_walk`, `_dotted_name_for_path` | `importlib`, `importlib.util`, `pathlib`, `sys`, `types.ModuleType` |
| `src/assertions/_targets.py` | `parse_target` (only) | `pathlib`, `types.ModuleType`, `_classify._resolve_dotted`, `_loaders._load_path`, `_loaders._load_path_for_walk`, `_walk._walk_directory`, `assertions._config.DiscoveryConfig` |

`_targets.py` shrinks from 207 lines to about 25.

## Test layout after the split

| Test file | New / existing | Tests for |
|-----------|----------------|-----------|
| `tests/test_walk.py` | new | `_walk_directory`, `_accepts_file`, exclusion logic |
| `tests/test_loaders.py` | new | `_exec_module_from_path`, `_dotted_name_for_path` |
| `tests/test_targets.py` | existing, slimmed | `parse_target` (integration: classification → walking/loading) |

Each test class moves to the file matching where its target lives.
Where a single existing class tests both a low-level helper and
`parse_target`, the helper-focused tests move and the
orchestrator-focused tests stay in `test_targets.py`.

There is no new `tests/test_classify.py` because no existing tests
target `_resolve_dotted` directly; coverage of dotted-name resolution
is carried by the `parse_target` integration tests in
`tests/test_targets.py`. Adding direct unit tests for `_resolve_dotted`
is deferred to a future test-improvement slice.

`tests/test_config.py` is unchanged.

## Behavior

No behavior change. Every public-internal name keeps its current
signature. The only change is which file contains the symbol.

## Validation

The proof of correctness is "all 136 existing tests pass without
modification beyond import updates, and `mypy` reports no issues".
No new tests are added in this slice — that would muddle the
"refactor only" boundary.

## Module layout

| File | Action | Purpose |
|------|--------|---------|
| `src/assertions/_classify.py` | create | `_resolve_dotted` |
| `src/assertions/_walk.py` | create | walking + path expansion |
| `src/assertions/_loaders.py` | create | module loading |
| `src/assertions/_targets.py` | rewrite | thin orchestrator (`parse_target` only) |
| `src/assertions/__main__.py` | modify | import `_build_exclude_set`, `_resolve_include_paths`, `_walk_directory` from `_walk`; `_load_path_for_walk` from `_loaders`; `parse_target` still from `_targets` |
| `tests/test_classify.py` | create | tests for `_resolve_dotted` |
| `tests/test_walk.py` | create | tests for walker + filters |
| `tests/test_loaders.py` | create | tests for loaders |
| `tests/test_targets.py` | modify | leaves `parse_target` integration tests, removes others |

## Acceptance

- `uv run python -m unittest discover -s tests` reports the same test
  count and the same pass result as before the split.
- `uv run mypy` reports no issues.
- `git grep` for the moved symbols inside `src/` and `tests/`
  confirms only the new module is the source.
- The four `examples/*.py` modules still run via the CLI.
