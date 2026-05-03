Changelog
=========

0.1.5 (2026-05-03)
------------------

**Improvements**
- Added convenience context manager method `__test_context__` for set-up and
  tear-down to be applied to all test methods.
- Added the ability to run plugins. (The first plugin, testsweet-django, will
  be available soon.)

0.1.4 (2026-04-30)
------------------

**Improvements**
- Improved output.
- Added `--help` command line option.
- Can be invoked using `testsweet`

**Documentation**
- Clarified that class context managers are treated like
  `setUpClass()`/`tearDownClass()`.

0.1.3 (2026-04-29)
------------------

**Improvements**
- Tightened typing and added py.typed marker

0.1.2 (2026-04-29)
------------------

**Documentation**
- Used absolute URLs in README.md to link to documentation on GitHub.
- Added CHANGELOG.md.
