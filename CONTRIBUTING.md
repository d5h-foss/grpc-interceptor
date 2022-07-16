# Running Tests

This will run the unit tests quickly:

```
poetry install
make tests
```

It doesn't run the entire test suite. See below for that.

# Making a Pull Request

Please bump the version number in `pyproject.toml` when you make a pull request. This is needed to give the package a new version.

Also run the full test / lint suite by running `nox`. This runs in Github Actions as well, but you'll get faster feedback by running it locally. It does take some time though, so I'd just do it when the code is finished but before creating a PR.
