Cleanup
=======

1. The internals don't match the API's restraint

src/assertions/_targets.py is 327 lines doing six different jobs: target
classification, dotted-name resolution, directory walking, package-aware
module loading, glob-pattern exclusion, grep subprocess invocation. The
README's promise of "explicit in its architecture" should apply to internals
too — a reader who opens this file won't see explicit boundaries.

I'd split into three files of ~80–100 lines each:
- _classify.py — parse_target, _resolve_dotted. Pure: string → Target-shape.
- _walk.py — _walk_directory, _enumerate_directory, _grep_*, exclusion logic.
- _loaders.py — _exec_module_from_path, _load_path_for_walk,
_dotted_name_for_path, sys.path insertion.

2. The CLI/discovery boundary is implicit

__main__.py reaches into five private names from _targets:

```python
from assertions._targets import (
    _build_exclude_set, _enumerate_directory, _load_path_for_walk,
    _resolve_include_paths, parse_target,
)
```

That's a smell. The _ prefix is doing documentation-of-shame work — there's
clearly a real interface here, it's just hidden. "Explicit in its
architecture" means the seam should be visible. I'd give the CLI a single
function:

def collect(argv: list[str], config: DiscoveryConfig) ->
Iterator[ModuleSelection]:
    """Yield (module, names) pairs for the CLI to run."""

Module loading, walking, grouping all stay behind it. The CLI shrinks from 84
lines to ~25.

3. The runner has more knowledge than it should

_runner.py is 100 lines and contains:
- _build_plan — selector resolution, Test-subclass introspection,
_public_methods lookup, LookupError raising. That's resolution, not running.
- _invoke — PARAMS_MARKER lookup, branch on whether params exist. That's
marker-knowledge leaking in.

Cleaner: each test unit yields its own (name, callable_to_invoke) pairs
through a uniform protocol. Param expansion is a partial per tuple. Class
methods are the iterator of a context-manager-wrapped scope. The runner
becomes one loop:

```python
def run(module, names=None):
    units = _resolve(module, names)  # in _targets
    return [(name, _safely(call)) for name, call in _expand(units)]
```

_runner.py shrinks to ~30 lines and Test/@test_params/@test_params_lazy plug
in via the same protocol.

4. Small idioms that fight Python

- _dotted_name_for_path returns (str | None, Path | None) where the two are
always both-None or both-set. Either return None for the loose-file case and a
tuple for the package case, or make a PackageInfo NamedTuple. The two-Nones
contract is documented in a comment but not in the type.
- _resolve_dotted is the trickiest function in the codebase — two state
machines (head/tail) plus special-case ModuleNotFoundError.name introspection.
It works, but it's the kind of code that bites in six months. Three explicit
phases (try full → walk down testing each prefix → assemble result) would be
longer but more readable.
- _invoke's try/except branches duplicate for params vs no-params. A for args
in (params or [()]): and a single try/except would be one branch.
- _add_to_groups is O(n²) per-target identity comparison. Tiny scale today; a
single defaultdict pass would be O(n) and cleaner.

5. Test's __init_subclass__ is subtly implicit

Subclassing Test mutates the class — adds TEST_MARKER = True. If a user does
class MyMixin(Test): ... for any reason, MyMixin gets discovered as a test.
There's no opt-out.

The README warns against magic. __init_subclass__ is a real Python feature,
but the side effect is invisible at the call site. A more explicit form:
require @test on the class too. Costs one more line per test class; gains
"you'll never accidentally turn something into a test by inheritance".

6. use_grep is a lot of weight for an opt-in optimization

Six tasks, four tool-specific argv shapes, subprocess handling, exit-code
interpretation, an indirection-shortcoming you have to document and accept.
~170 lines of production code plus tests for a feature that:
- Is off by default.
- Has a documented correctness caveat (indirection).
- Helps only on huge trees, which we don't have.

Pragmatically I'd have shipped the project without it and waited for someone
to hit a real "discovery is too slow" complaint. The configurability in the
rest of B.2 (include_paths, exclude_paths, test_files) already covers the same
need with no caveats.

The other side of this: it WAS designed cleanly (_enumerate_directory as the
seam, four tools as parallel argv-builders). If we'd skipped it, this list
would be shorter and the codebase smaller.

7. Tests are a lot, and tightly coupled

161 tests for ~777 lines of production code. Many test private helpers
directly (_grep_argv, _dotted_name_for_path, _walk_directory). A future split
(#1, #2) means many tests need to move with the helpers. That's fine but it's
a real cost to factor in when refactoring.

Some private-helper tests document behavior the public surface already
constrains (TestPublicMethodsCurrentBehavior for staticmethod/classmethod is
the clearest example) — these are observations, not contracts. They're labeled
as such, which is good. But several others (e.g. _grep_argv's exact argv
shape) could be replaced with one end-to-end test that runs the actual tool.

