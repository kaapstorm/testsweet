# Design: idiom-level cleanups

## Scope

Four small, independent improvements that align internal idioms with
Python conventions. No behavior change at the public API level; same
units run, same results, same exit codes.

The four:

- **(a) `_dotted_name_for_path` return shape**: replace
  `tuple[str | None, pathlib.Path | None]` (always-both-None or
  always-both-set) with `tuple[str, pathlib.Path] | None`. The caller
  branches on `is None`, not on a sentinel pair.
- **(b) `_resolve_dotted` rewrite**: replace the in-place
  `head_parts.pop()` / `tail_parts.insert(0, ...)` mutation loop with
  an explicit `range`-based slice over prefix lengths, and extract
  the "internal-import-error vs missing-prefix" check into a named
  helper. Same semantics, more linear flow.
- **(d) `_add_to_groups` → O(n) merge inside `discover_targets`**:
  replace the per-target linear scan with a single `dict[id(module),
  TargetGroup]` accumulation, exploiting `dict` insertion order. The
  `_add_to_groups` helper goes away.
- **(e) `resolve_units` flattens**: return
  `Iterator[tuple[str, Callable[[], Any]]]` instead of
  `list[Iterator[tuple[str, Callable[[], Any]]]]`. Use
  `itertools.chain.from_iterable` internally with `_build_plan`
  called eagerly above the chain. The runner loses one level of
  for-loop nesting.

In scope:

- Source changes in `_classify.py`, `_loaders.py`, `_targets.py`,
  `_resolve.py`, `_runner.py`.
- Test updates in `tests/test_loaders.py`, `tests/test_resolve.py`.
- No new tests; the existing tests are updated to match the new
  return shapes.

Out of scope:

- Public API changes (`assertions/__init__.py` is not touched).
- Renaming any of the four functions.
- Changes to `_runner.py` beyond the shape implied by `resolve_units`
  flattening.
- Behavior changes — every existing CLI scenario still works
  identically.

## Approach

Each cleanup stands alone. They land as four separate tasks so each
commit's diff is small and the test suite confirms behavior at every
checkpoint. Running order is intentional — (b) is the most contained
(no callers change), (a) and (d) update one or two callers each, (e)
touches both `_resolve.py` and `_runner.py`. Doing (e) last avoids
re-touching the runner while we're still moving things around.

## (a) `_dotted_name_for_path` return shape

### Current

```python
def _dotted_name_for_path(
    path: pathlib.Path,
) -> tuple[str | None, pathlib.Path | None]:
    parts: list[str] = [path.stem]
    parent = path.parent
    while (parent / '__init__.py').exists():
        parts.insert(0, parent.name)
        if parent.parent == parent:
            break
        parent = parent.parent
    if len(parts) == 1:
        return None, None
    return '.'.join(parts), parent
```

The two-Nones contract is documented in a comment but not in the
type. Callers must remember to guard both fields.

### After

```python
def _dotted_name_for_path(
    path: pathlib.Path,
) -> tuple[str, pathlib.Path] | None:
    parts: list[str] = [path.stem]
    parent = path.parent
    while (parent / '__init__.py').exists():
        parts.insert(0, parent.name)
        if parent.parent == parent:
            break
        parent = parent.parent
    if len(parts) == 1:
        # Loose file; caller falls back to spec_from_file_location.
        return None
    return '.'.join(parts), parent
```

### Caller change in `_loaders.py`

```python
def _load_path_for_walk(path: pathlib.Path) -> ModuleType:
    info = _dotted_name_for_path(path)
    if info is None:
        return _exec_module_from_path(path)
    dotted, rootdir = info
    rootdir_str = str(rootdir)
    if rootdir_str not in sys.path:
        sys.path.insert(0, rootdir_str)
    return importlib.import_module(dotted)
```

### Test updates in `tests/test_loaders.py`

- `test_returns_dotted_name_for_packaged_file`: `info =
  _dotted_name_for_path(target); self.assertIsNotNone(info); dotted,
  rootdir = info; ...`.
- `test_returns_none_for_loose_file`: `self.assertIsNone(
  _dotted_name_for_path(target))`.
- `test_top_level_package_file`: same shape as the packaged-file
  test.

## (b) `_resolve_dotted` rewrite

### Current

A 30-line while-loop that mutates `head_parts` (pops the last
segment) and `tail_parts` (inserts at the start) on each iteration,
plus a four-line inline test for "is this a missing-prefix error or
an internal import error inside the prefix".

### After

```python
import importlib
from types import ModuleType


def _resolve_dotted(
    target: str,
) -> tuple[ModuleType, list[str] | None]:
    parts = target.split('.')
    first_error: ModuleNotFoundError | None = None

    # Try each prefix from longest to shortest.
    for prefix_length in range(len(parts), 0, -1):
        head = '.'.join(parts[:prefix_length])
        tail_parts = parts[prefix_length:]
        try:
            module = importlib.import_module(head)
        except ModuleNotFoundError as exc:
            if not _is_missing_prefix_error(exc, head):
                # The prefix exists but raised inside its own
                # imports — propagate rather than mask as a bad
                # selector.
                raise
            if first_error is None:
                first_error = exc
            continue
        if not tail_parts:
            return module, None
        if len(tail_parts) > 2:
            raise LookupError(
                f'cannot resolve {target!r}: too many trailing '
                f'segments after module {head!r}'
            )
        return module, ['.'.join(tail_parts)]

    # No prefix imported. Re-raise the natural error.
    assert first_error is not None
    raise first_error


def _is_missing_prefix_error(
    exc: ModuleNotFoundError,
    head: str,
) -> bool:
    # The prefix itself is what's missing, vs an unrelated import
    # inside the prefix's module.
    return exc.name is not None and (
        exc.name == head or head.startswith(exc.name + '.')
    )
```

### What changes

- `range(len(parts), 0, -1)` replaces `head_parts.pop()` / `insert`
  mutation. Each iteration computes its own `head` and `tail_parts`
  via slicing.
- The four-line inline `if exc.name is None or not (...)` becomes a
  one-line `if not _is_missing_prefix_error(exc, head)` with a named
  helper.
- `first_error` is preserved so the "no prefix imports" exit re-raises
  the original error from the longest target (matches current
  behavior).

### Test updates

None. `tests/test_targets.py` exercises `_resolve_dotted` indirectly
through `parse_target`. The behaviors covered include:

- importable dotted module → `(module, None)`.
- single trailing segment → `(module, ['name'])`.
- two trailing segments → `(module, ['Class.method'])`.
- three trailing segments → `LookupError`.
- no importable prefix → `ModuleNotFoundError`.
- internal import error inside a real module →
  `ModuleNotFoundError` (the regression test `has_broken_import`).

All pass against the rewrite.

## (d) `_add_to_groups` → O(n) merge

### Current

```python
def _add_to_groups(
    groups: list[TargetGroup],
    module: ModuleType,
    names: list[str] | None,
) -> None:
    for i, (existing_module, existing_names) in enumerate(groups):
        if existing_module is module:
            if existing_names is None or names is None:
                groups[i] = (module, None)
            else:
                groups[i] = (module, existing_names + names)
            return
    groups.append((module, names))
```

Called once per `(module, names)` pair from `discover_targets`. Each
call linear-scans the existing list. Quadratic in the number of
targets.

### After

`_add_to_groups` is removed. `discover_targets` accumulates into a
`dict` keyed by `id(module)`:

```python
def discover_targets(
    argv: list[str],
    config: DiscoveryConfig,
) -> list[TargetGroup]:
    excluded = _build_exclude_set(config)
    raw: list[TargetGroup] = []
    if not argv:
        raw.extend(_bare_invocation(config, excluded))
    else:
        for arg in argv:
            raw.extend(parse_target(arg, config, excluded))

    # Group by module identity, preserving first-seen order via
    # dict insertion order. Whole-module entries (names is None)
    # win over selectors for the same module.
    by_id: dict[int, TargetGroup] = {}
    for module, names in raw:
        key = id(module)
        existing = by_id.get(key)
        if existing is None:
            by_id[key] = (module, names)
        else:
            _, existing_names = existing
            if existing_names is None or names is None:
                by_id[key] = (module, None)
            else:
                by_id[key] = (module, existing_names + names)
    return list(by_id.values())
```

Order is preserved by `dict` insertion semantics (Python 3.7+).
`id(module)` is a valid key as long as the modules stay alive — and
they do, because they're held by `raw` (and the returned list).

### Test updates

None. `tests/test_targets.py::TestDiscoverTargets` tests (`dedup`,
`module_then_selector_for_same_module_keeps_module`,
`two_selectors_same_module_merge_names`) all observe behavior
through `discover_targets`'s return value, which is unchanged.

## (e) `resolve_units` flattens

### Current

`resolve_units` returns a `list` of generators. The runner
double-loops:

```python
for unit_iter in resolve_units(module, names):
    for name, call in unit_iter:
        ...
```

### After

`resolve_units` returns a single iterator that yields `(name,
call)` pairs from all units, flattened:

```python
import itertools

def resolve_units(
    module: ModuleType,
    names: list[str] | None = None,
) -> Iterator[tuple[str, Callable[[], Any]]]:
    units = discover(module)
    if names is None:
        return itertools.chain.from_iterable(
            _expand_unit(unit, None) for unit in units
        )
    plan = _build_plan(units, names)
    return itertools.chain.from_iterable(
        _expand_unit(unit, plan[unit.__qualname__])
        for unit in units
        if unit.__qualname__ in plan
    )
```

`_build_plan` runs **outside** the `chain.from_iterable` argument —
the generator expression is materialized lazily, but `_build_plan`
is a synchronous call before `chain` is constructed. So validation
remains eager (before any yield), and `LookupError` for unmatched
selectors fires at `resolve_units(...)` call time, not at first
iteration.

### Runner change

```python
def run(
    module: ModuleType,
    names: list[str] | None = None,
) -> list[tuple[str, Exception | None]]:
    results: list[tuple[str, Exception | None]] = []
    for name, call in resolve_units(module, names):
        try:
            call()
        except Exception as exc:
            results.append((name, exc))
        else:
            results.append((name, None))
    return results
```

One level of for-loop nesting removed.

### Test updates in `tests/test_resolve.py`

The current tests destructure `generators[0]`, `generators[1]`, etc.
With flattening, they iterate the single iterator and check the
yielded `(name, call)` pairs. Concretely:

- `test_plain_function_yields_one_pair`: was `len(generators) == 2;
  list(generators[0]) == [...]`. Becomes `pairs = list(resolve_units(
  mod)); names = [n for n, _ in pairs]; self.assertIn('passes_one',
  names)`.
- `test_parameterized_function_yields_indexed_partials`: was
  `list(generators[0])`. Becomes `list(resolve_units(mod))`.
- `test_class_with_context_manager_brackets_methods`: was iterating
  `generators[0]`. Becomes iterating `resolve_units(mod)`.
- `test_class_method_selector_filters`: same shape.
- `test_unmatched_name_raises_lookup_error`: unchanged (LookupError
  fires at `resolve_units(...)` call, before any iteration).
- `test_validation_runs_before_any_iteration`: unchanged in spirit;
  the test verifies that `mod.CALLS` stays empty after the
  `LookupError` raises. Validation still happens before any
  generator runs.
- `test_class_form_wins_over_method_selector`: was iterating
  `generators[0]`. Becomes iterating `resolve_units(mod, names=...)`.
- `test_mixed_module_yields_one_generator_per_unit`: this test
  currently asserts `len(generators) == 2` — that semantic disappears.
  Renamed to `test_mixed_module_yields_pairs_in_order` and asserts
  `[name for name, _ in resolve_units(mod)] == ['free_function',
  'ClassUnit.method']`.
- `test_empty_module_returns_empty_list`: was
  `self.assertEqual(resolve_units(mod), [])`. Becomes
  `self.assertEqual(list(resolve_units(mod)), [])`.
- `test_no_names_means_no_filtering`: same shape, iterate the
  single iterator.

## Module layout

| File | Action | Purpose |
|------|--------|---------|
| `src/assertions/_classify.py` | rewrite | `_resolve_dotted` (b) plus `_is_missing_prefix_error` helper |
| `src/assertions/_loaders.py` | modify | `_dotted_name_for_path` return shape (a); `_load_path_for_walk` adapts |
| `src/assertions/_targets.py` | modify | `discover_targets` does its own dict-based merge (d); `_add_to_groups` removed |
| `src/assertions/_resolve.py` | modify | `resolve_units` flattens (e); imports `itertools` |
| `src/assertions/_runner.py` | modify | single for-loop (e) |
| `tests/test_loaders.py` | modify | `_dotted_name_for_path` test updates (a) |
| `tests/test_resolve.py` | modify | iteration-shape updates (e); rename one test class |

No new files. No tests added or removed; existing tests are updated
to match the new return shapes.

## Acceptance

- `_dotted_name_for_path` return type is `tuple[str, pathlib.Path] |
  None`. No `tuple[str | None, pathlib.Path | None]` anywhere.
- `_resolve_dotted` uses `range`-based prefix iteration and a named
  `_is_missing_prefix_error` helper.
- `_add_to_groups` no longer exists. `discover_targets` builds its
  groups dict in O(n).
- `resolve_units` returns an `Iterator`, not a `list[Iterator]`.
- `_runner.py` has a single for-loop in `run`.
- All previous tests pass (current count 158).
- `uv run mypy` reports no issues.
- Every existing CLI scenario behaves identically.
