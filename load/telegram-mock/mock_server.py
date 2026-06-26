"""Minimal Telegram Bot API stub for local load tests."""

import json
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

HOST = "0.0.0.0"
PORT = 8081
BOT_TOKEN_RE = re.compile(r"^/bot([^/]+)/(?P<method>[\w]+)$")


def _bot_id_from_token(token: str) -> int:
    prefix = token.split(":", 1)[0]
    if prefix.isdigit():
        return int(prefix)
    return 9_000_000_001


def _ok(result: object) -> bytes:
    return json.dumps({"ok": True, "result": result}).encode()


def _handle_method(method: str, token: str, body: bytes) -> bytes:
    bot_id = _bot_id_from_token(token)

    if method == "getMe":
        return _ok(
            {
                "id": bot_id,
                "is_bot": True,
                "first_name": "LoadBot",
                "username": f"load_bot_{bot_id}",
            }
        )

    if method in {"setWebhook", "deleteWebhook", "close", "logOut"}:
        return _ok(True)

    if method in {
        "sendMessage",
        "sendChatAction",
        "editMessageText",
        "answerCallbackQuery",
    }:
        return _ok(
            {
                "message_id": 1,
                "date": 1_700_000_000,
                "chat": {"id": 1, "type": "private"},
                "text": "ok",
            }
        )

    if method == "getUpdates":
        return _ok([])

    if method in {"setMyCommands", "deleteMyCommands", "getMyCommands"}:
        return _ok([] if method == "getMyCommands" else True)

    sys.stderr.write(f"telegram-mock: unhandled method={method}\n")
    return _ok(True)


class TelegramMockHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return

    def do_GET(self) -> None:
        self._dispatch()

    def do_POST(self) -> None:
        self._dispatch()

    def _dispatch(self) -> None:
        parsed = urlparse(self.path)
        match = BOT_TOKEN_RE.match(parsed.path)
        if match is None:
            self.send_response(404)
            self.end_headers()
            return

        token = match.group(1)
        method = match.group("method")
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else b""
        _ = parse_qs(parsed.query)

        payload = _handle_method(method, token, body)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), TelegramMockHandler)
    sys.stderr.write(f"telegram-mock listening on {HOST}:{PORT}\n")
    server.serve_forever()


if __name__ == "__main__":
    main()
