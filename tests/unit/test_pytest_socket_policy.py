from __future__ import annotations

from pathlib import Path

import pytest


pytest_plugins = ("pytester",)
REPO_ROOT = Path(__file__).resolve().parents[2]


def _write_test(path: Path, source: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")


@pytest.mark.socket_adapter
def test_collection_markers_enable_live_socket_but_keep_unit_blocked(
    pytester: pytest.Pytester,
) -> None:
    pytester.makeconftest(
        f"import sys\nsys.path.insert(0, {str(REPO_ROOT)!r})\n"
        "from tests.conftest import pytest_collection_modifyitems\n"
    )
    _write_test(
        pytester.path / "tests/live/test_live_socket.py",
        """
import socket


def test_live_socket_reaches_local_stack():
    connection = socket.socket()
    connection.settimeout(0.5)
    try:
        try:
            connection.connect(("127.0.0.2", 9))
        except ConnectionRefusedError:
            pass
        else:
            raise AssertionError("expected an unused local port")
    finally:
        connection.close()
""",
    )
    _write_test(
        pytester.path / "tests/unit/test_unit_socket.py",
        """
import socket

import pytest
from pytest_socket import SocketConnectBlockedError


def test_unit_socket_is_blocked():
    connection = socket.socket()
    try:
        with pytest.raises(SocketConnectBlockedError):
            connection.connect(("127.0.0.2", 9))
    finally:
        connection.close()
""",
    )

    result = pytester.runpytest_subprocess(
        "-q",
        "-n",
        "0",
        "--disable-socket",
        "--allow-hosts=127.0.0.1,localhost,::1",
    )

    result.assert_outcomes(passed=2)


@pytest.mark.socket_adapter
def test_unit_socket_guard_fails_when_block_error_is_swallowed(
    pytester: pytest.Pytester,
) -> None:
    pytester.makeconftest(
        f"import sys\nsys.path.insert(0, {str(REPO_ROOT)!r})\n"
        "from tests.conftest import _unit_socket_attempt_guard\n"
    )
    _write_test(
        pytester.path / "tests/unit/test_swallowed_socket.py",
        """
import socket


def test_swallowed_socket_error():
    connection = socket.socket()
    try:
        try:
            connection.connect(("127.0.0.2", 9))
        except RuntimeError:
            pass
    finally:
        connection.close()
""",
    )

    result = pytester.runpytest_subprocess(
        "-q",
        "-n",
        "0",
        "--disable-socket",
        "--allow-hosts=127.0.0.1,localhost,::1",
    )

    result.assert_outcomes(passed=1, errors=1)
    result.stdout.fnmatch_lines(["*attempted socket connection(s): connect*"])
