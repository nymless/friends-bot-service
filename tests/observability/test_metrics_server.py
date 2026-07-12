import socket
import urllib.request

from friends_bot_service.infra.observability.setup import start_metrics_server


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def test_metrics_server_exposes_prometheus_text():
    port = _free_port()
    start_metrics_server("127.0.0.1", port)

    with urllib.request.urlopen(f"http://127.0.0.1:{port}/metrics") as response:
        body = response.read().decode()

    assert response.status == 200
    assert "friends_bot_handler_invocations_total" in body
    assert "friends_bot_draw_handler_duration_seconds" in body
