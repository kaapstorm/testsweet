Changelog
=========

Unreleased
----------

### Improvements

- Added tests and documentation for the assertion explainer.


[0.2.2] (2026-06-27)
--------------------

### Bug Fixes

- Fixed loading a test file by path (e.g. `testsweet path/to/tests.py`)
  when the module uses relative imports.
- Fixed resolving dotted targets (e.g. `testsweet tests.foo`) when run
  via the installed `testsweet` console script.

[0.2.2]: https://github.com/kaapstorm/testsweet/releases/tag/v0.2.2


[0.2.1] (2026-06-27)
--------------------

### Improvements

- Switched type checking from mypy to ty
- Extended settings for linting and tightened type hints
- Added "authors" and "keywords" to `pyproject.toml`
- Tweaked CHANGELOG.md formatting
- Automated GitHub releases


[0.2.1]: https://github.com/kaapstorm/testsweet/releases/tag/v0.2.1


[0.2.0] (2026-05-04)
--------------------

### Improvements

- Added `@skip`, `@xfail`, and `@tag` decorators for marking tests.
- Added command-line tag filtering: `-t`/`--tag` to include and
  `-T`/`--exclude-tag` to exclude (both repeatable). A class-level
  `@tag` propagates to every method on the class.
- Discovery now rejects orphan modifier decorators — a callable
  carrying `@skip`, `@xfail`, `@tag`, or `@params` without `@test`
  raises `ConfigurationError` rather than being silently ignored.

### Deprecations

- `@test_params` and `@test_params_lazy` were renamed to `@params`
  and `@params_lazy` and no longer imply `@test`. Stack `@test` on
  top of `@params(...)` (or `@params_lazy(...)`) on the functions
  or methods you want discovered.

[0.2.0]: https://github.com/kaapstorm/testsweet/releases/tag/v0.2.0


[0.1.5] (2026-05-03)
--------------------

### Improvements

- Added convenience context manager method `__test_context__` for set-up and
  tear-down to be applied to all test methods.
- Added the ability to run plugins. (The first plugin, testsweet-django, will
  be available soon.)

[0.1.5]: https://github.com/kaapstorm/testsweet/releases/tag/v0.1.5


[0.1.4] (2026-04-30)
--------------------

### Improvements

- Improved output.
- Added `--help` command line option.
- Can be invoked using `testsweet`

### Documentation

- Clarified that class context managers are treated like
  `setUpClass()`/`tearDownClass()`.

[0.1.4]: https://github.com/kaapstorm/testsweet/releases/tag/v0.1.4


[0.1.3] (2026-04-29)
--------------------

### Improvements

- Tightened typing and added py.typed marker

[0.1.3]: https://github.com/kaapstorm/testsweet/releases/tag/v0.1.3


[0.1.2] (2026-04-29)
--------------------

### Documentation

- Used absolute URLs in README.md to link to documentation on GitHub.
- Added CHANGELOG.md.

[0.1.2]: https://github.com/kaapstorm/testsweet/releases/tag/v0.1.2
