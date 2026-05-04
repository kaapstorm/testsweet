# Outcome decorators and richer reporting

Target: testsweet 0.2.0.

## Motivation

testsweet currently has two decorators (`@test`, `@test_params*`) and a
binary outcome model (pass / fail). Real test suites need at least:

- **Skip**: a test the author knows shouldn't run yet (or only on some
  Pythons / OSes).
- **Expected failure** (`xfail`): a test that documents a known bug. If
  it fails, that's expected; if it passes, that's news.
- **Tags**: arbitrary string labels for grouping (`'slow'`,
  `'integration'`, etc.). Filtering by tag isn't part of this design,
  but the marker shape needs to be ready.
- **Error vs failure**: an `AssertionError` is a test author's claim
  being violated; a `TypeError` is the test author's *code* being
  broken. Reporters everywhere distinguish these — testsweet currently
  doesn't.

This design adds those, and standardizes on **one marker per
decorator**. `@test_params` (which currently sets two markers) is
split into `@test` + `@params`.

## Decorator reference

All decorators live in `testsweet` (re-exported from `__init__.py`).

### `@test` (unchanged)

Marks a function or class as a test unit. No new behavior.

### `@skip` / `@skip(...)`

Marks a test as skipped. The body never runs.

```python
@test
@skip
def not_yet_implemented(): ...

@test
@skip(reason='waiting on upstream PR')
def waits_for_upstream(): ...

@test
@skip(if_=sys.version_info < (3, 12))
def py312_only(): ...

@test
@skip(if_=sys.platform == 'win32', reason='POSIX-only')
def posix_only(): ...
```

Signature follows the well-trodden bare-or-called pattern (cf.
`functools.cache`):

```python
def skip(*args, reason=None, if_=True): ...
```

- Bare `@skip`: marker stored with `condition=True`, no reason.
- `@skip(reason='...')`: marker stored with reason.
- `@skip(if_=expr)`: `expr` evaluated at decoration time (eager). If
  False, the marker is still attached but with `condition=False` —
  the runner ignores it.
- Combined: `@skip(if_=cond, reason='...')`.

Marker: `__testsweet_skip__` — a frozen `SkipMarker` dataclass
(`reason: str | None`, `condition: bool`).

### `@xfail` / `@xfail(...)`

Marks a test as expected to fail. If the test raises, the outcome is
recorded as `xfailed` (treated as passing for exit-code purposes). If
the test passes, the outcome is `xpassed` — **always a failure**: the
`@xfail` decoration is now lying, and that's the kind of drift
testsweet wants to surface, not paper over. Either remove the marker
(the bug is fixed) or fix the test (it was wrongly marked).

```python
@test
@xfail
def known_broken(): ...

@test
@xfail(reason='known bug, see issue #42')
def issue_42(): ...

@test
@xfail(if_=sys.platform == 'win32')
def fails_on_windows(): ...
```

Signature:

```python
def xfail(*args, reason=None, if_=True): ...
```

Marker: `__testsweet_xfail__` — a frozen `XFailMarker` dataclass
(`reason: str | None`, `condition: bool`).

Note: this is more strict than pytest's default. The "test sometimes
passes, sometimes fails" use case (genuine flakiness) is not what
`@xfail` is for; if testsweet ever needs to model it, that belongs in
a separate decorator (e.g. `@flaky`).

### `@params([...])`

Replaces `@test_params([...])`. Materializes the iterable at
decoration time. Does **not** set the test marker — must stack with
`@test`.

```python
@test
@params([(1, 2), (3, 4)])
def adds_correctly(a, b):
    assert a + b > 0
```

Marker: `__testsweet_params__` — a tuple of argument tuples.

### `@params_lazy([...])`

Replaces `@test_params_lazy([...])`. Iterable consumed at run time.
Same marker name as `@params` — the runner doesn't care which one
populated it.

### `@tag(*names)`

Adds string tags. Stack `@tag` calls or pass multiple in one call.
Tags are stored but **not yet used by the runner** in 0.2.0 — they're
groundwork for future filtering (`testsweet --tag slow`).

```python
@test
@tag('slow')
@tag('integration')
def long_running(): ...

@test
@tag('slow', 'integration')
def equivalently(): ...
```

Marker: `__testsweet_tags__` — a `frozenset[str]`.

## Outcome model

Result tuples stay `list[tuple[str, Exception | None]]`. New outcome
states are encoded as Exception subclasses placed (not raised) into
the slot. The reporter dispatches on `isinstance`.

| Outcome  | Slot value                           | Meaning |
|----------|--------------------------------------|---------|
| pass     | `None`                               | test ran without raising |
| skipped  | `Skipped(reason)`                    | `@skip` marker active |
| xfailed  | `XFailed(actual_exc, reason)`        | `@xfail` active and test raised |
| xpassed  | `XPassed(reason)`                    | `@xfail` active but test passed (failure) |
| failure  | `AssertionError` subclass            | author's claim was violated |
| error    | any other `Exception`                | author's code is broken |

Three new public classes in `testsweet`:

```python
class Skipped(Exception):
    def __init__(self, reason: str | None = None): ...

class XFailed(Exception):
    def __init__(
        self, actual: Exception, reason: str | None = None,
    ): ...

class XPassed(Exception):
    def __init__(self, reason: str | None = None): ...
```

`Skipped`/`XFailed`/`XPassed` are **constructed**, not raised by user
code. They go into the result slot and are pattern-matched by the
reporter. They subclass `Exception` purely so the existing tuple type
doesn't have to change.

Exit-code semantics:
- pass / skipped / xfailed → not a failure.
- failure / error / xpassed → exit 1.

## Reporter changes

`_report.format_result_line(name, exc)` returns one of:

```
mod.test_name ... ok
mod.test_name ... skipped: not yet implemented
mod.test_name ... xfailed: known bug, see issue #42
mod.test_name ... XPASSED: known bug, see issue #42
mod.test_name ... FAIL: AssertionError: 1 == 2
mod.test_name ... ERROR: TypeError: 'int' object is not iterable
```

`_report.print_failure_detail` fires for `FAIL`, `ERROR`, and
`XPASSED`. The `XPASSED` detail block reads:

> Test was marked `@xfail` but passed. Either the underlying bug is
> fixed (remove the marker) or the test was wrongly marked.

`xfailed` and `skipped` don't get a detail block.

A new summary line at end of run:

```
10 passed, 2 failed, 1 error, 3 skipped, 1 xfailed, 0 xpassed
```

Helper: `_report.summarize(results) -> str`.

## Runner integration

Inside `_runner.run`, before calling `wrap_unit(name)`:

```python
skip_marker = _get_skip_marker(call)
if skip_marker is not None and skip_marker.condition:
    results.append((name, Skipped(skip_marker.reason)))
    continue

xfail_marker = _get_xfail_marker(call)
if xfail_marker is not None and xfail_marker.condition:
    try:
        with wrap_unit(name):
            call()
    except Exception as exc:
        results.append(
            (name, XFailed(exc, xfail_marker.reason))
        )
    else:
        results.append((name, XPassed(xfail_marker.reason)))
    continue

# unmarked path, today's behavior
try:
    with wrap_unit(name):
        call()
except Exception as exc:
    results.append((name, exc))
else:
    results.append((name, None))
```

Note: skip and xfail markers attach to the underlying function. For
parametrized tests (`@params`), every parameter combo inherits the
same marker — they're all skipped, or all xfailed. Per-combo
conditional skipping is out of scope for 0.2.

For class-method tests, the class's `__enter__`/`__exit__` still
fires; only the method body is skipped. `__test_context__` is not
entered for skipped methods (no point, the test doesn't run).

The marker-extraction helpers go in a new `_outcomes.py` module so
the runner doesn't import from each decorator file. Same module
houses `Skipped`/`XFailed`/`XPassed`.

## Discovery-time validation

The biggest footgun in this redesign: forgetting `@test` above
`@params(...)`. The function gets parameter metadata but is never
discovered. To catch this, `discover()` scans for orphan markers and
raises `ConfigurationError`:

```python
def discover(module):
    tests = []
    for name, value in vars(module).items():
        if not callable(value):
            continue
        is_test = getattr(value, TEST_MARKER, False) is True
        has_params = hasattr(value, PARAMS_MARKER)
        has_skip = hasattr(value, SKIP_MARKER)
        has_xfail = hasattr(value, XFAIL_MARKER)
        has_tags = hasattr(value, TAGS_MARKER)
        has_modifier = has_params or has_skip or has_xfail or has_tags
        if has_modifier and not is_test:
            raise ConfigurationError(
                f"{module.__name__}.{name} has a testsweet modifier "
                f"({_first_marker(value)}) but is not decorated with "
                f"@test."
            )
        if is_test:
            tests.append(value)
    return tests
```

This shifts a silent "test doesn't run" into a loud `ConfigurationError`
at startup — same posture as the plugin loader.

## Migration from `@test_params` / `@test_params_lazy`

Both removed in 0.2.0. testsweet is pre-1.0 and has no known external
users; a hard break is cheaper than carrying deprecated shims.

| Before                              | After                                |
|-------------------------------------|--------------------------------------|
| `@test_params([...])`               | `@test` + `@params([...])`           |
| `@test_params_lazy([...])`          | `@test` + `@params_lazy([...])`      |

Release-notes call-out plus a short migration paragraph in
`getting-started.md`.

testsweet-django and other downstream plugins don't use these
decorators (they're test-author-facing, not plugin-facing), so the
plugin-protocol contract is unaffected.

## Public API surface (after 0.2.0)

Added to `testsweet.__init__`:

```
Skipped
XFailed
XPassed
params
params_lazy
skip
tag
xfail
```

Removed from `testsweet.__init__`:

```
test_params
test_params_lazy
```

`Plugin`, `ENTRY_POINT_GROUP`, `DiscoveryConfig`, `ConfigurationError`,
`catch_exceptions`, `catch_warnings`, `discover`, `run`, `test`
unchanged.

## File-level changes

- `_markers.py` — gain `SKIP_MARKER`, `XFAIL_MARKER`, `TAGS_MARKER`
  string constants. (`PARAMS_MARKER` already lives in `_params.py`;
  may move here for symmetry.)
- `_skip.py` — new. Defines `skip`, `SkipMarker`.
- `_xfail.py` — new. Defines `xfail`, `XFailMarker`.
- `_tag.py` — new. Defines `tag`.
- `_params.py` — `params` and `params_lazy`. Drops the `TEST_MARKER`
  setattr in both.
- `_outcomes.py` — new. Defines `Skipped`, `XFailed`, `XPassed`, plus
  helpers `evaluate_skip(call)` and `evaluate_xfail(call)` returning
  the active marker or None.
- `_runner.py` — branches on skip / xfail markers as above.
- `_report.py` — extends `format_result_line`; adds `summarize`;
  narrows `print_failure_detail` to FAIL / ERROR / strict XPASS.
- `_discover.py` — orphan-marker check.
- `__init__.py` — re-exports the new names; drops the old.
- `tests/` — coverage for each decorator, each outcome path, the
  reporter formatting, and the orphan-marker error.
- `docs/reference.md`, `docs/getting-started.md` — new sections,
  migration note.

## Out of scope for 0.2.0

- Filtering tests by tag from CLI (`--tag`, `--exclude-tag`).
- Per-parameter-combo skip / xfail.
- Late-bound `if_=` (callable instead of value).
- Skip/xfail as plugin extension points (today's design hardcodes
  them; that's fine for now).
- Intermittent / flaky tests. `@xfail` is for tests known to fail
  consistently; if testsweet ever needs to model "sometimes passes,
  sometimes fails," that belongs in a separate decorator.
- Output format for tags in result lines (e.g. `--show-tags`). Tags
  are stored, not shown.
- Color output. `xfailed` would read better in yellow, `XPASSED` in
  red, but `_report.py` already takes a `file` argument so a future
  TTY-aware variant can layer in without API change.

## Decisions

- `@skip(if_=False)` attaches the marker with `condition=False` so
  introspection (e.g. tooling, future `--list` modes) can see "this
  is conditionally skipped, but the condition is False right now."
