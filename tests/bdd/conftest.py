"""Shared pytest-bdd fixtures for BDD test suite.

Provides:
- ``cli_runner``: a Click ``CliRunner`` instance for invoking the CLI.
- ``output_dir``: a temporary directory scoped to the test, used for solution output files.
"""

from __future__ import annotations

import pathlib

import pytest
from click.testing import CliRunner


@pytest.fixture
def cli_runner() -> CliRunner:
    """Return a Click CliRunner with isolated filesystem disabled.

    The runner uses ``mix_stderr=False`` so stdout and stderr are
    separately accessible in BDD step assertions.
    """
    return CliRunner(mix_stderr=False)


@pytest.fixture
def output_dir(tmp_path: pathlib.Path) -> pathlib.Path:
    """Return a temporary directory for solution output files.

    Each test gets a fresh, isolated directory so tests cannot
    interfere via shared output paths.
    """
    return tmp_path
