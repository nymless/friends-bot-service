"""Minimal Telegram Bot API stub for local load tests."""

from __future__ import annotations

import json
import re
import sys
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
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


@dataclass
class _BotQueue:
    updates: deque[dict[str, Any]] = field(default_factory=deque)
    cond: threading.Condition = field(default_factory=threading.Condition)


_queues: dict[int, _BotQueue] = defaultdict(_BotQueue)
_queues_lock = threading.Lock()


def _queue_for_bot(bot_id: int) -> _BotQueue:
    with _queues_lock:
        return _queues[bot_id]


def reset_queues() -> None:
    with _queues_lock:
        _queues.clear()


def enqueue_update(bot_id: int, update: dict[str, Any]) -> None:
    queue = _queue_for_bot(bot_id)
    with queue.cond:
        queue.updates.append(update)
        queue.cond.notify_all()


def get_updates_for_bot(
    bot_id: int,
    *,
    offset: int,
    limit: int,
    timeout: int,
) -> list[dict[str, Any]]:
    queue = _queue_for_bot(bot_id)
    deadline = time.monotonic() + max(timeout, 0)

    with queue.cond:
        while True:
            pending = [item for item in queue.updates if item["update_id"] >= offset]
            pending.sort(key=lambda item: item["update_id"])
            if pending:
                batch = pending[:limit]
                delivered_ids = {item["update_id"] for item in batch}
                queue.updates = deque(
                    item
                    for item in queue.updates
                    if item["update_id"] not in delivered_ids
                )
                return batch

            remaining = deadline - time.monotonic()
            if timeout <= 0 or remaining <= 0:
                return []

            queue.cond.wait(timeout=min(1.0, remaining))


def _parse_json_body(body: bytes) -> dict[str, Any]:
    if not body:
        return {}
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return {}


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
        payload = _parse_json_body(body)
        offset = int(payload.get("offset", 0))
        limit = int(payload.get("limit", 100))
        timeout = int(payload.get("timeout", 0))
        result = get_updates_for_bot(
            bot_id,
            offset=offset,
            limit=limit,
            timeout=timeout,
        )
        return _ok(result)

    if method in {"setMyCommands", "deleteMyCommands", "getMyCommands"}:
        return _ok([] if method == "getMyCommands" else True)

    sys.stderr.write(f"telegram-mock: unhandled method={method}\n")
    return _ok(True)


def _read_json_body(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length", 0))
    raw = handler.rfile.read(length) if length else b""
    return _parse_json_body(raw)


def _handle_load_route(path: str, handler: BaseHTTPRequestHandler) -> bool:
    if path == "/_load/reset" and handler.command == "POST":
        reset_queues()
        payload = _ok(True)
        handler.send_response(200)
        handler.send_header("Content-Type", "application/json")
        handler.send_header("Content-Length", str(len(payload)))
        handler.end_headers()
        handler.wfile.write(payload)
        return True

    if path == "/_load/inject" and handler.command == "POST":
        data = _read_json_body(handler)
        bot_id = int(data["bot_id"])
        update = data["update"]
        enqueue_update(bot_id, update)
        payload = _ok(True)
        handler.send_response(200)
        handler.send_header("Content-Type", "application/json")
        handler.send_header("Content-Length", str(len(payload)))
        handler.end_headers()
        handler.wfile.write(payload)
        return True

    return False


class TelegramMockHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return

    def do_GET(self) -> None:
        self._dispatch()

    def do_POST(self) -> None:
        self._dispatch()

    def _dispatch(self) -> None:
        parsed = urlparse(self.path)
        if _handle_load_route(parsed.path, self):
            return

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
