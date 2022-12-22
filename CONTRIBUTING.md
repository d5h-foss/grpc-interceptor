# Running Tests

This will run the unit tests quickly:

```
poetry install
make tests
```

It doesn't run the entire test suite. See below for that.

# Making a Pull Request

Please bump the version number in `pyproject.toml` when you make a pull request. This is needed to give the package a new version.

Also run lint checks and mypy before pushing. This runs in Github Actions as well, but you'll get faster feedback by running it locally. To do this, run `nox -s lint` and
`nox -s mypy-3.x`, for whatever version of Python you have installed. For example, if
you're using Python 3.9, run `nox -s mypy-3.9`. If you need to make formatting changes,
you can run `nox -s black`. Note that `nox` isn't installed via `poetry`, due to
the way it works, so you'll need to install it globally. If you don't want to install
`nox`, you can do all this in docker. For example, you can run this to mount the current
directory into /app and work from there:

```
docker run --rm -it --mount type=bind,src="$(pwd)",dst=/app python:3.9 bash
```

# Adding Tests

Add both a sync and async version if applicable. You can follow the examples in many
tests for this. Search for `aio` to find one. Assuming the test applies to both sync
and async code, it will need to create a different test interceptor depending on the
value of `aio`. Then just remember to pass `aio_server=aio` to `dummy_client`. The
rest of the test can be the same for both sync and async. This is because the tests
create a client which calls a server. The client doesn't care whether the server is
sync or async.

# On Changing Dependencies

I want to keep this library very small, not just in terms of its own code, but in terms
of the code it pulls in. Having many dependencies is a burden to users. It increases
installation time (especially when solving constraints with newer pip or poetry). It
increases the likelihood of dependency conflicts, and generally just introduces more
that can go wrong. Hence, this library depends on as little as possible, and can
hopefully stay that way.
