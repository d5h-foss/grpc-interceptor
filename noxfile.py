import tempfile

import nox


nox.options.sessions = "lint", "mypy", "safety", "tests"


@nox.session(python=["3.8", "3.7", "3.6"])
def tests(session):
    args = session.posargs or ["--cov"]
    session.run("poetry", "install", "--no-dev", external=True)
    install_with_constraints(
        session, "coverage[toml]", "grpcio-tools", "pytest", "pytest-cov"
    )
    session.run("pytest", *args)


SOURCE_CODE = ["src", "tests", "noxfile.py"]


@nox.session(python="3.8")
def black(session):
    args = session.posargs or SOURCE_CODE
    install_with_constraints(session, "black")
    session.run("black", *args)


@nox.session(python="3.8")
def lint(session):
    args = session.posargs or SOURCE_CODE
    install_with_constraints(
        session, "flake8", "flake8-bandit", "flake8-bugbear", "flake8-import-order"
    )
    session.run("flake8", *args)


@nox.session(python=["3.8", "3.7", "3.6"])
def mypy(session):
    args = session.posargs or SOURCE_CODE
    install_with_constraints(session, "mypy")
    session.run("mypy", *args)


@nox.session(python="3.8")
def safety(session):
    with tempfile.NamedTemporaryFile() as requirements:
        session.run(
            "poetry",
            "export",
            "--dev",
            "--format=requirements.txt",
            "--without-hashes",
            f"--output={requirements.name}",
            external=True,
        )
        install_with_constraints(session, "safety")
        session.run("safety", "check", f"--file={requirements.name}", "--full-report")


def install_with_constraints(session, *args, **kwargs):
    with tempfile.NamedTemporaryFile() as requirements:
        session.run(
            "poetry",
            "export",
            "--dev",
            "--format=requirements.txt",
            f"--output={requirements.name}",
            external=True,
        )
        session.install(f"--constraint={requirements.name}", *args, **kwargs)
