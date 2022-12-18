"""Nox sessions."""

from contextlib import contextmanager
from pathlib import Path
import tempfile
from typing import List
from uuid import uuid4

import nox
import toml


nox.options.sessions = "lint", "mypy", "tests", "xdoctest", "mindeps"
PY_VERSIONS = ["3.9", "3.8", "3.7", "3.6.1"]
PY_LATEST = "3.9"


@nox.session(python=PY_VERSIONS)
def tests(session):
    """Run the test suite."""
    args = session.posargs or ["--cov"]
    poetry_install(session)
    install_with_constraints(
        session, "coverage", "grpcio-tools", "pytest", "pytest-cov"
    )
    session.run("pytest", *args)


@nox.session(python=PY_VERSIONS)
def xdoctest(session) -> None:
    """Run examples with xdoctest."""
    args = session.posargs or ["all"]
    poetry_install(session)
    install_with_constraints(session, "xdoctest")
    session.run("python", "-m", "xdoctest", "grpc_interceptor", *args)


def poetry_install(session):
    """Install this project via poetry."""
    if session.python.startswith("3.6."):
        # https://github.com/python-poetry/poetry/issues/4242
        session.run("poetry", "add", "setuptools", external=True)
    session.run("poetry", "install", "--no-dev", external=True)


@nox.session(python=PY_LATEST)
def coverage(session):
    """Upload coverage data."""
    install_with_constraints(session, "coverage", "codecov")
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


@nox.session(python="3.6.1")
def mindeps(session):
    """Run test with minimum versions of dependencies."""
    deps = _parse_minimum_dependency_versions()
    session.install(*deps)
    session.run("pytest", env={"PYTHONPATH": "src"})


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


def _parse_minimum_dependency_versions() -> List[str]:
    pyproj = toml.load("pyproject.toml")
    dependencies = pyproj["tool"]["poetry"]["dependencies"]
    dev_dependencies = pyproj["tool"]["poetry"]["dev-dependencies"]
    min_deps = []

    for deps in (dependencies, dev_dependencies):
        for dep, constraint in deps.items():
            if dep == "python":
                continue

            if not isinstance(constraint, str):
                # Don't install deps with python contraints, because they're always for
                # newer versions on python.
                if "python" in constraint:
                    continue
                constraint = constraint["version"]

            if constraint.startswith("^") or constraint.startswith("~"):
                version = constraint[1:]
            elif constraint.startswith(">="):
                version = constraint[2:]
            else:
                version = constraint

            min_deps.append(f"{dep}=={version}")

    return min_deps
