#!/usr/bin/env python3
"""Minimal Telegram webhook receiver for the documentation example."""

from __future__ import annotations

import json
import logging
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

HOST = "0.0.0.0"
PORT = 8080
MAX_BODY_BYTES = 1_000_000
WEBHOOK_SECRET = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("telegram-webhook-demo")


class Handler(BaseHTTPRequestHandler):
    server_version = "certify-reverse-telegram-demo/1"

    def _json_response(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        if self.path == "/health":
            self._json_response(HTTPStatus.OK, {"ok": True, "service": "telegram-webhook"})
            return
        self._json_response(
            HTTPStatus.NOT_FOUND,
            {"ok": False, "error": "use GET /health or POST /webhook"},
        )

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        if self.path != "/webhook":
            self._json_response(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not found"})
            return

        supplied_secret = self.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if not WEBHOOK_SECRET or supplied_secret != WEBHOOK_SECRET:
            self._json_response(HTTPStatus.FORBIDDEN, {"ok": False, "error": "invalid secret"})
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._json_response(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid length"})
            return
        if content_length <= 0 or content_length > MAX_BODY_BYTES:
            self._json_response(
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                {"ok": False, "error": "request body size is invalid"},
            )
            return

        try:
            update = json.loads(self.rfile.read(content_length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._json_response(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid JSON"})
            return

        update_id = update.get("update_id") if isinstance(update, dict) else None
        message = update.get("message") if isinstance(update, dict) else None
        chat_id = None
        if isinstance(message, dict) and isinstance(message.get("chat"), dict):
            chat_id = message["chat"].get("id")

        log.info("accepted Telegram update_id=%r chat_id=%r", update_id, chat_id)
        self._json_response(HTTPStatus.OK, {"ok": True})

    def log_message(self, format: str, *args: object) -> None:
        log.info("client=%s %s", self.client_address[0], format % args)


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    log.info("listening on http://%s:%d", HOST, PORT)
    server.serve_forever()


if __name__ == "__main__":
    main()
