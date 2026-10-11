"""No test may open a network connection."""

import socket
from typing import Any

import pytest


@pytest.fixture(autouse=True)
def disable_network(monkeypatch: Any) -> None:
    def blocked(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("Network is disabled in fixture tests")

    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)
