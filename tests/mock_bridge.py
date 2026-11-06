"""A mock Switch Agent Bridge for Ember's tests (stdlib http.server).

Implements exactly the endpoints Ember uses, with the shapes from
``docs/official/internals/agent-protocol.md``:

* POST /agents/register-known        (registration-token bearer)
* POST /agents                       (full-profile fallback door)
* GET  /agents/{id}/ops              (operation discovery)
* POST /agents/{id}/ops/{operation}  (recorded; canned room behaviour)
* POST /agents/{id}/connection/beat  (recorded)
* GET  /agents/{id}/events           (SSE: connection_state, then one
                                      scripted mention event, then
                                      keepalive comments until disconnect)

Everything is recorded on the server object so tests can assert on it.
Binds to 127.0.0.1 on an ephemeral port; no network beyond localhost.
"""

from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

REG_TOKEN = "test-registration-token"
API_KEY = "test-api-key"
AGENT_ID = "agent-ember-test"
ROOM_ID = "room-nightshift"

OPERATIONS = {
    "list_rooms": {"description": "List rooms", "input_schema": {}},
    "connect_to_room": {"description": "Connect", "input_schema": {}},
    "list_roles": {"description": "List roles", "input_schema": {}},
    "define_role": {"description": "Define role", "input_schema": {}},
    "assume_role": {"description": "Assume role", "input_schema": {}},
    "read_context": {"description": "Read context", "input_schema": {}},
    "post_message": {"description": "Post message", "input_schema": {}},
    "create_room_document": {"description": "Create doc", "input_schema": {}},
}

DEFAULT_CONTEXT = {
    "threads": [
        {
            "root": {
                "id": "m1", "kind": "message", "sender": "@alice:switch.local",
                "sender_name": "alice",
                "body": "v0.4 ships tomorrow — auth PR is in review.",
                "timestamp": 1, "attachments": [],
            },
            "replies": [],
        },
        {
            "root": {
                "id": "m2", "kind": "message",
                "sender": "@claude-reviewer:switch.local",
                "sender_name": "claude-reviewer",
                "body": "Heads up: the token refresh test is still blocking v0.4 on CI.",
                "timestamp": 2, "attachments": [],
            },
            "replies": [],
        },
    ],
    "truncated": False,
    "oldest_timestamp": 1,
}


class MockBridge(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, mention_body: str = "@ember what's the status?"):
        super().__init__(("127.0.0.1", 0), _Handler)
        self.mention_body = mention_body
        self.context = json.loads(json.dumps(DEFAULT_CONTEXT))
        self.ops_calls: list[dict] = []       # {operation, args, connection_id}
        self.beats: list[dict] = []
        self.registrations: list[dict] = []   # {path, body}
        self._events_sent = False
        self.lock = threading.Lock()

    @property
    def url(self) -> str:
        host, port = self.server_address
        return f"http://{host}:{port}"

    def ops_named(self, name: str) -> list[dict]:
        with self.lock:
            return [c for c in self.ops_calls if c["operation"] == name]

    def record_op(self, operation: str, args: dict, connection_id) -> None:
        with self.lock:
            self.ops_calls.append(
                {"operation": operation, "args": args,
                 "connection_id": connection_id}
            )


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    # Silence the default stderr access log.
    def log_message(self, *args):  # noqa: D102
        pass

    @property
    def bridge(self) -> MockBridge:
        return self.server  # type: ignore[return-value]

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def _bearer(self) -> str:
        auth = self.headers.get("Authorization") or ""
        return auth[7:] if auth.startswith("Bearer ") else ""

    # ── routes ──────────────────────────────────────────────────────────

    def do_POST(self):  # noqa: N802 (http.server naming)
        path = self.path.split("?", 1)[0]
        if path == "/agents/register-known":
            return self._register(known=True)
        if path == "/agents":
            return self._register(known=False)
        if path == f"/agents/{AGENT_ID}/connection/beat":
            if self._bearer() != API_KEY:
                return self._send_json(401, {"detail": "bad api key"})
            body = self._read_json()
            with self.bridge.lock:
                self.bridge.beats.append(body)
            return self._send_json(
                200, {"ok": True, "rooms": [ROOM_ID], "cursor": 0}
            )
        if path.startswith(f"/agents/{AGENT_ID}/ops/"):
            if self._bearer() != API_KEY:
                return self._send_json(401, {"detail": "bad api key"})
            operation = path.rsplit("/", 1)[-1]
            args = self._read_json()
            connection_id = self.headers.get("X-Switch-Connection-Id")
            self.bridge.record_op(operation, args, connection_id)
            return self._send_json(
                200, {"result": self._op_result(operation, args)}
            )
        return self._send_json(404, {"detail": f"no route {path}"})

    def _register(self, known: bool):
        if self._bearer() != REG_TOKEN:
            return self._send_json(401, {"detail": "Invalid registration token"})
        body = self._read_json()
        with self.bridge.lock:
            self.bridge.registrations.append(
                {"path": self.path, "body": body}
            )
        return self._send_json(200, {"id": AGENT_ID, "api_key": API_KEY})

    def _op_result(self, operation: str, args: dict):
        if operation == "list_rooms":
            return [{"room_id": ROOM_ID, "name": "nightshift",
                     "description": "NightShift demo room",
                     "connected": False, "archived": False}]
        if operation == "connect_to_room":
            return {"agent_id": AGENT_ID, "room_id": args.get("room_id"),
                    "name": "nightshift", "participants": [],
                    "roles": [], "warning": None}
        if operation == "list_roles":
            # release-manager deliberately absent: Ember must define it.
            return [{"name": "reviewer", "exclusive": False,
                     "instructions_preview": "Review PRs",
                     "held_by": [], "assumable_by_me": True}]
        if operation == "define_role":
            return {"status": "defined", "name": args.get("name")}
        if operation == "assume_role":
            return {"role": args.get("role"), "instructions": "wrap the day"}
        if operation == "read_context":
            return self.bridge.context
        if operation == "post_message":
            return {"event_id": "evt-posted-1"}
        if operation == "create_room_document":
            return {"document_id": "doc-1"}
        return {"ok": True}

    def do_GET(self):  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path == "/health":
            return self._send_json(200, {"ok": True})
        if path == f"/agents/{AGENT_ID}/ops":
            if self._bearer() != API_KEY:
                return self._send_json(401, {"detail": "bad api key"})
            return self._send_json(200, {"operations": OPERATIONS})
        if path == f"/agents/{AGENT_ID}/events":
            if self._bearer() != API_KEY:
                return self._send_json(401, {"detail": "bad api key"})
            return self._events()
        return self._send_json(404, {"detail": f"no route {path}"})

    def _events(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        try:
            state = {
                "connection_id": "conn-test-1",
                "agent_id": AGENT_ID,
                "scope": "all",
                "filter": "all",
                "rooms": [ROOM_ID],
                "cursor": 0,
                "generation": 1,
                "heartbeat_interval_seconds": 2,
            }
            self.wfile.write(
                f"event: connection_state\ndata: {json.dumps(state)}\n\n"
                .encode("utf-8")
            )
            self.wfile.flush()
            with self.bridge.lock:
                first = not self.bridge._events_sent
                self.bridge._events_sent = True
            if first:
                event = {
                    "type": "message",
                    "room_id": ROOM_ID,
                    "bridge_id": None,
                    "channel_type": "channel_public",
                    "sequence": 1,
                    "payload": {
                        "addressed": True,
                        "sender": "@alice:switch.local",
                        "sender_name": "alice",
                        "message_id": "msg-mention-1",
                        "body": self.bridge.mention_body,
                        "timestamp": 1700000000000,
                        "thread_id": None,
                        "attachments": [],
                    },
                }
                self.wfile.write(
                    f"id: 1\nevent: message\ndata: {json.dumps(event)}\n\n"
                    .encode("utf-8")
                )
                self.wfile.flush()
            # Hold the stream open with keepalives until the client leaves.
            while True:
                time.sleep(0.2)
                self.wfile.write(b": keepalive\n\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            return


def start_mock(mention_body: str = "@ember what's the status?"):
    """Start a MockBridge on an ephemeral localhost port (daemon thread)."""
    bridge = MockBridge(mention_body=mention_body)
    thread = threading.Thread(target=bridge.serve_forever, daemon=True)
    thread.start()
    return bridge
