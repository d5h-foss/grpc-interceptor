"""Sphinx configuration."""

import re


project = "grpc-interceptor"
author = "Dan Hipschman"
copyright = f"2020, {author}"
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
]


def setup(app):
    """Sphinx setup."""
    app.connect("autodoc-skip-member", skip_member)


def skip_member(app, what, name, obj, skip, options):
    """Ignore ugly auto-generated doc strings from namedtuple."""
    doc = getattr(obj, "__doc__", "") or ""  # Handle when __doc__ is missing on None
    is_namedtuple_docstring = bool(re.fullmatch("Alias for field number [0-9]+", doc))
    return is_namedtuple_docstring or skip
