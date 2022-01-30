"""Nox sessions."""

from contextlib import contextmanager
from pathlib import Path
import tempfile
from uuid import uuid4

import nox


nox.options.sessions = "lint", "mypy", "safety", "tests", "xdoctest"
PY_VERSIONS = ["3.9", "3.8", "3.7", "3.6"]
PY_LATEST = "3.9"


@nox.session(python=PY_VERSIONS)
def tests(session):
    """Run the test suite."""
    args = session.posargs or ["--cov"]
    session.run("poetry", "install", "--no-dev", external=True)
    install_with_constraints(
        session, "coverage[toml]", "grpcio-tools", "pytest", "pytest-cov"
    )
    session.run("pytest", *args)


@nox.session(python=PY_VERSIONS)
def xdoctest(session) -> None:
    """Run examples with xdoctest."""
    args = session.posargs or ["all"]
    session.run("poetry", "install", "--no-dev", external=True)
    install_with_constraints(session, "xdoctest")
    session.run("python", "-m", "xdoctest", "grpc_interceptor", *args)


@nox.session(python=PY_LATEST)
def coverage(session):
    """Upload coverage data."""
    install_with_constraints(session, "coverage[toml]", "codecov")
    session.run("coverage", "xml", "--fail-under=0")
    session.run("codecov", *session.posargs)


@nox.session(python=PY_LATEST)
def docs(session):
    """Build the documentation."""
    session.run("poetry", "install", "--no-dev", "-E", "testing", external=True)
    install_with_constraints(session, "sphinx")
    session.run("sphinx-build", "docs", "docs/_build")


SOURCE_CODE = ["src", "tests", "noxfile.py", "docs/conf.py"]


@nox.session(python=PY_LATEST)
def black(session):
    """Run black code formatter."""
    args = session.posargs or SOURCE_CODE
    install_with_constraints(session, "black")
    session.run("black", *args)


@nox.session(python=PY_LATEST)
def lint(session):
    """Lint using flake8."""
    args = session.posargs or SOURCE_CODE
    install_with_constraints(
        session,
        "flake8",
        "flake8-bandit",
        "flake8-bugbear",
        "flake8-docstrings",
        "flake8-import-order",
    )
    session.run("flake8", *args)


@nox.session(python=PY_VERSIONS)
def mypy(session):
    """Type-check using mypy."""
    args = session.posargs or SOURCE_CODE
    install_with_constraints(session, "mypy")
    session.run("mypy", *args)


@nox.session(python=PY_LATEST)
def safety(session):
    """Scan dependencies for insecure packages."""
    with _temp_file() as requirements:
        session.run(
            "poetry",
            "export",
            "--dev",
            "--format=requirements.txt",
            "--without-hashes",
            f"--output={requirements}",
            external=True,
        )
        install_with_constraints(session, "safety")
        session.run("safety", "check", f"--file={requirements}", "--full-report")


def install_with_constraints(session, *args, **kwargs):
    """Install packages constrained by Poetry's lock file."""
    with _temp_file() as requirements:
        session.run(
            "poetry",
            "export",
            "--dev",
            "--format=requirements.txt",
            f"--output={requirements}",
            "--without-hashes",
            external=True,
        )
        session.install(f"--constraint={requirements}", *args, **kwargs)


@contextmanager
def _temp_file():
    # NamedTemporaryFile doesn't work on Windows.
    path = Path(tempfile.gettempdir()) / str(uuid4())
    try:
        yield path
    finally:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
