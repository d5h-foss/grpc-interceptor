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

# Adding Tests

Add both a sync and async version if applicable.

# On Changing Dependencies

I want to keep this library very small, not just in terms of its own code, but in terms
of the code it pulls in. Hence, it depends on very, very little, and I'd like to keep
it that way.

I also try hard to keep this library compatible with Python 3.6. It's sometimes a pain,
but people out there are still using it. I'd rather they can use this library, than
require a newer version just to make the code a tiny bit simpler.
