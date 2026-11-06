"""Switch Agent Bridge client — the raw protocol, stdlib only.

Implements, per ``docs/official/internals/agent-protocol.md``:

* ``POST /agents/register-known`` — registration token as bearer; the
  returned ``api_key`` is shown once, so it is persisted immediately to
  the state file (``.ember-state.json``, chmod 0600, gitignored).
  Fallback: ``POST /agents`` with a full ``always_on`` integration
  profile when the server rejects the known ``agent_type`` (400) — the
  doc's lower-level door for agents that are not a known CLI.
* ``GET  /agents/{id}/ops`` — operation discovery.
* ``POST /agents/{id}/ops/{operation}`` — invocation; arguments are the
  body itself (unwrapped), connection id in ``X-Switch-Connection-Id``.
* ``GET  /agents/{id}/events`` — the SSE stream. The client generates the
  connection id (a UUID) once, persists it, and reuses it across
  reconnects; ``Last-Event-ID`` carries the resume cursor.
* ``POST /agents/{id}/connection/beat`` — heartbeat every 2 s. A 404/409
  means the connection is dead: reopen the stream, don't retry the beat.
"""

from __future__ import annotations

import http.client
import json
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Callable, Iterator

from .config import Config


class EmberHTTPError(Exception):
    def __init__(self, status: int, detail: Any = ""):
        super().__init__(f"HTTP {status}: {detail}")
        self.status = status
        self.detail = detail


def _log(message: str) -> None:
    print(f"[ember] {message}", file=sys.stderr, flush=True)


class SwitchClient:
    def __init__(self, config: Config):
        self.config = config
        self.base = config.server_url.rstrip("/")
        self.agent_id: str | None = None
        self.api_key: str | None = None
        self.connection_id: str | None = None
        self.cursor: int = 0
        self.generation: int | None = None
        self._load_state()

    # ── state file ──────────────────────────────────────────────────────

    def _load_state(self) -> None:
        path = self.config.state_path
        if not path.is_file():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            _log(f"ignoring unreadable state file {path}: {exc}")
            return
        if data.get("server_url") not in (None, self.base):
            _log("state file is for a different server; ignoring it")
            return
        self.agent_id = data.get("agent_id")
        self.api_key = data.get("api_key")
        self.connection_id = data.get("connection_id")
        if isinstance(data.get("cursor"), int):
            self.cursor = data["cursor"]

    def _save_state(self) -> None:
        path = self.config.state_path
        data = {
            "server_url": self.base,
            "agent_id": self.agent_id,
            "api_key": self.api_key,
            "connection_id": self.connection_id,
            "cursor": self.cursor,
            "name": self.config.name,
        }
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        try:
            path.chmod(0o600)
        except OSError:
            pass

    @property
    def registered(self) -> bool:
        return bool(self.agent_id and self.api_key)

    def ensure_connection_id(self) -> str:
        if not self.connection_id:
            self.connection_id = str(uuid.uuid4())
            if self.registered:
                self._save_state()
        return self.connection_id

    # ── low-level HTTP ──────────────────────────────────────────────────

    def _request(
        self,
        method: str,
        path: str,
        body: Any = None,
        *,
        token: str | None = None,
        extra_headers: dict | None = None,
        timeout: float = 15.0,
    ) -> Any:
        url = f"{self.base}{path}"
        data = None
        headers = {"Accept": "application/json"}
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        bearer = token if token is not None else self.api_key
        if bearer:
            headers["Authorization"] = f"Bearer {bearer}"
        if extra_headers:
            headers.update(extra_headers)
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            detail: Any = raw
            try:
                detail = json.loads(raw).get("detail", raw)
            except (ValueError, AttributeError):
                pass
            raise EmberHTTPError(exc.code, detail) from exc
        if not raw.strip():
            return None
        return json.loads(raw)

    # ── registration ────────────────────────────────────────────────────

    def register(self, overwrite: bool = False) -> dict:
        """Register Ember and persist the one-time API key.

        Primary door: POST /agents/register-known (registration token).
        If the bridge rejects the known agent_type (400 — Switch only
        knows its CLI provider types), fall back to POST /agents with a
        full always_on integration profile, per the protocol doc.
        """
        if not self.config.registration_token:
            raise ValueError(
                "EMBER_REGISTRATION_TOKEN is not set; cannot register"
            )
        token = self.config.registration_token
        body = {
            "agent_type": self.config.agent_type,
            "name": self.config.name,
            "description": (
                "Ember — NightShift's local-model release-manager agent. "
                "Hand-coded against the raw Switch agent protocol; runs on "
                "a local LLM and spends no cloud tokens."
            ),
            "options": {},
            "overwrite": overwrite,
        }
        try:
            result = self._request(
                "POST", "/agents/register-known", body, token=token
            )
        except EmberHTTPError as exc:
            if exc.status != 400:
                raise
            _log(
                "register-known rejected the agent_type "
                f"({exc.detail}); falling back to POST /agents "
                "with a full always_on profile"
            )
            fallback_body = {
                "name": self.config.name,
                "description": body["description"],
                "connector_type": "Ember (raw protocol)",
                "integration_profile": {
                    "connection_model": "always_on",
                    "message_exchange": True,
                    "pre_invocation_mediation": [],
                    "post_invocation_mediation": [],
                    "event_reporting": [],
                },
                "tools": [],
                "models": [],
                "metadata": {},
                "overwrite": overwrite,
            }
            result = self._request("POST", "/agents", fallback_body, token=token)
        self.agent_id = result["id"]
        self.api_key = result["api_key"]
        self.ensure_connection_id()
        self._save_state()
        _log(f"registered as agent {self.agent_id}; key persisted to "
             f"{self.config.state_path}")
        return result

    def ensure_registered(self) -> None:
        if not self.registered:
            self.register()

    # ── operations ──────────────────────────────────────────────────────

    def list_ops(self) -> dict:
        self.ensure_registered()
        result = self._request("GET", f"/agents/{self.agent_id}/ops")
        return result.get("operations", result)

    def call_op(self, name: str, args: dict | None = None) -> Any:
        """POST /agents/{id}/ops/{name} — body is the arguments object
        itself; the result is unwrapped from {"result": ...}."""
        self.ensure_registered()
        headers = {}
        if self.connection_id:
            headers["X-Switch-Connection-Id"] = self.connection_id
        result = self._request(
            "POST",
            f"/agents/{self.agent_id}/ops/{urllib.parse.quote(name, safe='')}",
            args or {},
            extra_headers=headers,
        )
        if isinstance(result, dict) and "result" in result:
            return result["result"]
        return result

    # Convenience wrappers with the repo's exact operation names and
    # signatures (core/switch_core/bridges/agent/operations/definitions.py).
    def list_rooms(self) -> list:
        return self.call_op("list_rooms", {})

    def connect_to_room(self, room_id: str) -> dict:
        return self.call_op("connect_to_room", {"room_id": room_id})

    def list_roles(self) -> list:
        return self.call_op("list_roles", {})

    def define_role(self, name: str, instructions: str, exclusive: bool = False) -> Any:
        return self.call_op(
            "define_role",
            {"name": name, "instructions": instructions, "exclusive": exclusive},
        )

    def assume_role(self, role: str) -> Any:
        # The repo's op is assume_role(role=...) — there is no take_role.
        return self.call_op("assume_role", {"role": role})

    def read_context(self, limit: int = 50, room_id: str | None = None) -> dict:
        args: dict[str, Any] = {"limit": limit}
        if room_id:
            args["room_id"] = room_id
        result = self.call_op("read_context", args)
        return result if isinstance(result, dict) else {"threads": []}

    def post_message(self, body: str, thread_id: str | None = None) -> Any:
        args: dict[str, Any] = {"body": body}
        if thread_id:
            args["thread_id"] = thread_id
        return self.call_op("post_message", args)

    def create_room_document(
        self, name: str, description: str, instructions: str, content: str
    ) -> Any:
        # The repo's document op is create_room_document (scoped to the
        # connected room) — there is no generic "create document" op.
        return self.call_op(
            "create_room_document",
            {
                "name": name,
                "description": description,
                "instructions": instructions,
                "content": content,
            },
        )

    # ── heartbeat ───────────────────────────────────────────────────────

    def beat_once(self) -> dict:
        """POST /agents/{id}/connection/beat. Raises EmberHTTPError with
        status 404/409 when the connection is dead (reopen, don't retry)."""
        self.ensure_registered()
        body: dict[str, Any] = {
            "connection_id": self.ensure_connection_id(),
            "cursor": self.cursor,
        }
        if self.generation is not None:
            body["generation"] = self.generation
        return self._request(
            "POST", f"/agents/{self.agent_id}/connection/beat", body
        )

    # ── SSE event stream ────────────────────────────────────────────────

    def events_url(self, rooms: list[str] | None = None) -> str:
        params = {
            "connection_id": self.ensure_connection_id(),
            "scope": "all",
            "filter": "all",
            "start_from": "head",
            "client": "ember",
            "client_version": "0.4.0",
        }
        if rooms:
            params["rooms"] = ",".join(rooms)
        query = urllib.parse.urlencode(params)
        return f"/agents/{self.agent_id}/events?{query}"

    def stream_events(
        self,
        rooms: list[str] | None = None,
        *,
        socket_timeout: float = 20.0,
    ) -> Iterator[dict]:
        """Yield frames as {"event", "data", "id"} dicts.

        Control frames (connection_state, gap, evicted, ...) carry no SSE
        id; domain events carry their sequence both as the SSE id and as
        data.sequence. Keepalive comments are consumed silently. Raises
        OSError / http.client errors on a dropped socket — the caller's
        reconnect loop owns backoff.
        """
        self.ensure_registered()
        parts = urllib.parse.urlsplit(self.base)
        host = parts.hostname or "localhost"
        port = parts.port or (443 if parts.scheme == "https" else 80)
        conn_cls = (
            http.client.HTTPSConnection
            if parts.scheme == "https"
            else http.client.HTTPConnection
        )
        conn = conn_cls(host, port, timeout=socket_timeout)
        path = (parts.path.rstrip("/") if parts.path else "") + self.events_url(rooms)
        headers = {
            "Accept": "text/event-stream",
            "Authorization": f"Bearer {self.api_key}",
        }
        if self.cursor:
            headers["Last-Event-ID"] = str(self.cursor)
        conn.request("GET", path, headers=headers)
        response = conn.getresponse()
        if response.status != 200:
            detail = response.read().decode("utf-8", errors="replace")
            conn.close()
            raise EmberHTTPError(response.status, detail[:500])
        try:
            event_type: str | None = None
            event_id: str | None = None
            data_lines: list[str] = []
            while True:
                raw_line = response.readline()
                if not raw_line:
                    break  # socket closed by server
                line = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
                if line == "":
                    if event_type is not None or data_lines:
                        data_text = "\n".join(data_lines)
                        data: Any = data_text
                        try:
                            data = json.loads(data_text)
                        except ValueError:
                            pass
                        seq = None
                        if event_id is not None:
                            try:
                                seq = int(event_id)
                            except ValueError:
                                seq = None
                        if seq is not None:
                            self.cursor = max(self.cursor, seq)
                        yield {
                            "event": event_type or "message",
                            "data": data,
                            "id": seq,
                        }
                    event_type, event_id, data_lines = None, None, []
                    continue
                if line.startswith(":"):
                    continue  # keepalive comment
                if line.startswith("id:"):
                    event_id = line[3:].strip()
                elif line.startswith("event:"):
                    event_type = line[6:].strip()
                elif line.startswith("data:"):
                    data_lines.append(line[5:].lstrip())
        finally:
            try:
                conn.close()
            except Exception:
                pass


class HeartbeatThread(threading.Thread):
    """Beats every ``interval`` seconds. On a 404/409 (dead connection) it
    fires ``on_dead`` once and keeps beating — the agent's reconnect loop
    reopens the stream, after which beats succeed again. Network errors
    are logged, never fatal."""

    def __init__(
        self,
        client: SwitchClient,
        interval: float = 2.0,
        on_dead: Callable[[int], None] | None = None,
    ):
        super().__init__(daemon=True, name="ember-heartbeat")
        self.client = client
        self.interval = interval
        self.on_dead = on_dead
        self.stop_event = threading.Event()
        self.beat_count = 0
        self._dead_notified = False

    def run(self) -> None:
        while not self.stop_event.is_set():
            try:
                self.client.beat_once()
                self.beat_count += 1
                self._dead_notified = False
            except EmberHTTPError as exc:
                if exc.status in (404, 409):
                    if not self._dead_notified:
                        self._dead_notified = True
                        _log(f"heartbeat refused ({exc.status}); "
                             "connection is dead, stream must reopen")
                        if self.on_dead is not None:
                            try:
                                self.on_dead(exc.status)
                            except Exception:
                                pass
                else:
                    _log(f"heartbeat failed: {exc}")
            except Exception as exc:  # noqa: BLE001 — never kill the thread
                _log(f"heartbeat error: {exc}")
            self.stop_event.wait(self.interval)

    def stop(self) -> None:
        self.stop_event.set()
