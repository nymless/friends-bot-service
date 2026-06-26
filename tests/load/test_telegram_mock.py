import importlib.util
import json
import sys
import threading
import urllib.request
from pathlib import Path

_MOCK_PATH = (
    Path(__file__).resolve().parents[2] / "load" / "telegram-mock" / "mock_server.py"
)
_SPEC = importlib.util.spec_from_file_location("telegram_mock_server", _MOCK_PATH)
assert _SPEC and _SPEC.loader
mock_server = importlib.util.module_from_spec(_SPEC)
sys.modules["telegram_mock_server"] = mock_server
_SPEC.loader.exec_module(mock_server)


def _post_json(url: str, payload: dict) -> dict:
    body = json.dumps(payload).encode()
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read().decode())


def _get_updates(port: int, token: str, *, offset: int = 0, timeout: int = 0) -> list:
    body = json.dumps({"offset": offset, "limit": 100, "timeout": timeout}).encode()
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}/bot{token}/getUpdates",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request) as response:
        data = json.loads(response.read().decode())
    assert data["ok"] is True
    return data["result"]


def test_get_updates_returns_injected_update():
    mock_server.reset_queues()
    server = mock_server.ThreadingHTTPServer(
        ("127.0.0.1", 0),
        mock_server.TelegramMockHandler,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    token = "1000000:AAloadtestfake"

    try:
        _post_json(
            f"http://127.0.0.1:{port}/_load/inject",
            {
                "bot_id": 1_000_000,
                "update": {
                    "update_id": 42,
                    "message": {"message_id": 42, "text": "/stats"},
                },
            },
        )

        updates = _get_updates(port, token)
        assert len(updates) == 1
        assert updates[0]["update_id"] == 42

        updates_again = _get_updates(port, token, offset=43)
        assert updates_again == []
    finally:
        server.shutdown()
