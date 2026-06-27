# Guidelines for Claude Code

## Commands

Start commands with `uv run ...` to run in the uv virtualenv.

* Python: `uv run python ...`
* Run tests: `uv run testsweet`
* Run linter: `uv run ruff check`
* Run type checker: `uv run ty check src/ tests/`

## File locations

| File                 | Path                                           |
|----------------------|------------------------------------------------|
| Design specs         | claude/specs/YYYY-MM-DD_design-name.md         |
| Implementation plans | claude/plans/YYYY-MM-DD_implementation-name.md |
