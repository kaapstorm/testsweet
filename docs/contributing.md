Contributing
============

This project uses [uv](https://docs.astral.sh/uv/) for dependency and
environment management.

Sync the project (creates a virtualenv and installs dependencies,
including the `dev` group):

```shell
uv sync
```

Activate the pre-commit hook so `ruff format` runs automatically before
each commit:

```shell
uv run pre-commit install
```
