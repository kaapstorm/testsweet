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


Running the tests
-----------------

The test suite is self-hosted on testsweet:

```shell
uv run python -m testsweet
```

A small `unittest`-based shim is also kept, so that the package stays
runnable via the stdlib runner even if a regression breaks testsweet's
own discovery or runner:

```shell
uv run python -m unittest discover
```

The shim only verifies that the public API can be imported. Real
coverage lives in the testsweet suite.
