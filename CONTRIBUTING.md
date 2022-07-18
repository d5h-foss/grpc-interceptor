# Running Tests

This will run the unit tests quickly:

```
poetry install
make tests
```

It doesn't run the entire test suite. See below for that.

# Making a Pull Request

Please bump the version number in `pyproject.toml` when you make a pull request. This is needed to give the package a new version.

Also run lint checks and mypy before pushing. This runs in Github Actions as well, but you'll get faster feedback by running it locally. To do this, run `nox -s lint-3.x` and
`nox -s mypy-3.x`, for whatever version of Python you have installed. For example, if
you're using Python 3.9, run `nox -s lint-3.9`. If you need to make formatting changes,
you can run ``nox -s black-3.x`. Note that `nox` isn't installed via `poetry`, due to
the way it works, so you'll need to install it globally.

# Adding Tests

Add both a sync and async version if applicable.

# On Changing Dependencies

I want to keep this library very small, not just in terms of its own code, but in terms
of the code it pulls in. Having many dependencies is a burden to users. It increases
installation time (especially when solving constraints with newer pip or poetry). It
increases the likelihood of dependency conflicts, and makes it harder to upgrade. Hence,
this library depends on as little as possible, and I'd like to keep it that way. I will
likely not merge PRs that add dependencies.

I also try hard to keep this library compatible with Python 3.6. It's sometimes a pain,
but people out there are still using it. I'd rather they can use this library, and it's
usually not that much work to make the code compatible.
