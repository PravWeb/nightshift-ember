"""EmberAgent — the event loop that turns Switch frames into room work.

Flow per the protocol doc: open the stream (declaring scope/filter on the
URL), read ``connection_state``, claim a room with ``connect_to_room``,
define/assume the configured role, then act on addressed ``message``
events: ``read_context`` → brain → ``post_message`` (threaded). A message
containing ``!wrap`` (or the word "wrap") runs the release wrap instead:
git log → release-notes document → wrap summary in chat.

Robustness rules from the task: reconnect with backoff on SSE drop, and a
bad message must never crash the loop — every handler is wrapped.
"""

from __future__ import annotations

import sys
import threading
import time
from typing import Any

from . import brain as brain_module
from .client import EmberHTTPError, HeartbeatThread, SwitchClient
from .config import Config
from .brain import flatten_context
from .tools import (
    compose_release_notes,
    compose_wrap_summary,
    extract_blockers,
    git_log,
    latest_tag,
)


def _log(message: str) -> None:
    print(f"[ember] {message}", file=sys.stderr, flush=True)


def is_wrap_command(body: str) -> bool:
    lowered = (body or "").lower()
    return "!wrap" in lowered or "wrap" in lowered


def is_addressed_to_me(event_data: dict, my_name: str) -> bool:
    payload = event_data.get("payload") or {}
    if payload.get("addressed"):
        return True
    body = (payload.get("body") or "").lower()
    return f"@{my_name.lower()}" in body or my_name.lower() in body


class EmberAgent:
    def __init__(self, config: Config, client: SwitchClient | None = None):
        self.config = config
        self.client = client or SwitchClient(config)
        self.room_id: str | None = config.room_id or None
        self.stop_event = threading.Event()
        self.connection_dead = threading.Event()
        self.heartbeat: HeartbeatThread | None = None
        self._startup_done_for: str | None = None  # connection_id

    # ── startup: claim room, define/take role ───────────────────────────

    def startup_sequence(self) -> None:
        """connect_to_room + define_role (if missing) + assume_role.

        Called once per (re)connection, after connection_state arrives.
        Every step is best-effort: a role that is already defined or held
        must not stop Ember from working the room."""
        client = self.client
        try:
            rooms = client.list_rooms()
        except Exception as exc:  # noqa: BLE001
            _log(f"list_rooms failed: {exc}")
            rooms = []
        if not self.room_id:
            for room in rooms or []:
                if isinstance(room, dict) and room.get("room_id"):
                    self.room_id = room["room_id"]
                    break
        if self.room_id:
            try:
                client.connect_to_room(self.room_id)
                _log(f"connected to room {self.room_id}")
            except Exception as exc:  # noqa: BLE001
                _log(f"connect_to_room failed: {exc}")
        role = self.config.role
        if role:
            try:
                roles = client.list_roles()
                names = {
                    r.get("name") for r in roles or [] if isinstance(r, dict)
                }
                if role not in names:
                    client.define_role(
                        role, self.config.role_instructions, exclusive=True
                    )
                    _log(f"defined role {role!r} (exclusive)")
            except Exception as exc:  # noqa: BLE001
                _log(f"role definition step failed: {exc}")
            try:
                client.assume_role(role)
                _log(f"assumed role {role!r}")
            except Exception as exc:  # noqa: BLE001
                _log(f"assume_role({role!r}) failed: {exc}")

    # ── message handling ────────────────────────────────────────────────

    def _is_own_message(self, payload: dict) -> bool:
        sender_name = (payload.get("sender_name") or "").lower()
        return sender_name == self.config.name.lower()

    def handle_event(self, frame: dict) -> None:
        """Dispatch one stream frame. Never raises."""
        try:
            event_type = frame.get("event")
            data = frame.get("data")
            if not isinstance(data, dict):
                return
            if event_type == "connection_state":
                generation = data.get("generation")
                if isinstance(generation, int):
                    self.client.generation = generation
                conn_id = data.get("connection_id") or self.client.connection_id
                if self._startup_done_for != conn_id:
                    self._startup_done_for = conn_id
                    self.startup_sequence()
                return
            if event_type in ("evicted",):
                _log(f"evicted frame: {data}; will reconnect")
                self.connection_dead.set()
                return
            if event_type in ("gap", "subscription_changed", "room_released"):
                _log(f"control frame {event_type}: {data}")
                return
            if data.get("type") == "message" or event_type == "message":
                self.handle_message(data)
            elif data.get("type") == "command" or event_type == "command":
                payload = data.get("payload") or {}
                command = (payload.get("command") or "").lower()
                if command in ("wrap", "!wrap"):
                    self.do_wrap(thread_id=payload.get("thread_id"))
            # room_join / task_* frames: handled by ignoring (per doc, the
            # task protocol is present but not ready for use).
        except Exception as exc:  # noqa: BLE001 — a bad frame never kills us
            _log(f"error handling frame {frame.get('event')!r}: {exc}")

    def handle_message(self, event_data: dict) -> None:
        payload = event_data.get("payload") or {}
        if self._is_own_message(payload):
            return
        if not is_addressed_to_me(event_data, self.config.name):
            return
        body = payload.get("body") or ""
        thread_id = payload.get("thread_id") or payload.get("message_id")
        if is_wrap_command(body):
            self.do_wrap(thread_id=thread_id)
            return
        context = self._read_context_safe()
        reply = brain_module.get_reply(
            body,
            context,
            brain_mode=self.config.brain,
            llm_base_url=self.config.llm_base_url,
            llm_model=self.config.llm_model,
        )
        self.client.post_message(reply, thread_id=thread_id)

    def _read_context_safe(self) -> dict:
        try:
            return self.client.read_context(limit=50)
        except Exception as exc:  # noqa: BLE001
            _log(f"read_context failed: {exc}")
            return {"threads": []}

    # ── the wrap ────────────────────────────────────────────────────────

    def do_wrap(self, thread_id: str | None = None) -> str:
        """Compose release notes from the demo repo + room context, create
        the room document, and post the wrap summary. Returns the posted
        summary text."""
        context = self._read_context_safe()
        entries = flatten_context(context)
        blockers = extract_blockers(entries)
        commits: list[dict] = []
        since_tag: str | None = None
        if self.config.demo_repo:
            try:
                since_tag = latest_tag(self.config.demo_repo)
                commits = git_log(self.config.demo_repo, since_tag=since_tag)
            except Exception as exc:  # noqa: BLE001
                _log(f"git log failed: {exc}")
        else:
            _log("EMBER_DEMO_REPO not set; wrapping with no commits")
        version = self.config.release
        notes = compose_release_notes(
            commits, version=version, since_tag=since_tag, blockers=blockers
        )
        document_name = f"{version} release notes"
        try:
            self.client.create_room_document(
                name=document_name,
                description=f"Release notes for {version} (NightShift wrap)",
                instructions=(
                    "Read this for what shipped in this release and what "
                    "is still blocking it. Maintained by Ember, the "
                    "release-manager agent."
                ),
                content=notes,
            )
            _log(f"created room document {document_name!r}")
        except Exception as exc:  # noqa: BLE001
            _log(f"create_room_document failed: {exc}")
        summary = compose_wrap_summary(
            commits, version=version, blockers=blockers,
            document_name=document_name,
        )
        self.client.post_message(summary, thread_id=thread_id)
        return summary

    # ── run loop ────────────────────────────────────────────────────────

    def run_forever(self) -> None:
        """Stream → handle → reconnect with backoff, until stopped."""
        self.client.ensure_registered()
        self.client.ensure_connection_id()
        self.heartbeat = HeartbeatThread(
            self.client,
            interval=self.config.heartbeat_seconds,
            on_dead=lambda status: self.connection_dead.set(),
        )
        self.heartbeat.start()
        backoff = 1.0
        try:
            while not self.stop_event.is_set():
                self.connection_dead.clear()
                try:
                    _log("opening event stream…")
                    for frame in self.client.stream_events():
                        if self.stop_event.is_set() or self.connection_dead.is_set():
                            break
                        self.handle_event(frame)
                    _log("event stream closed")
                    backoff = 1.0
                except EmberHTTPError as exc:
                    _log(f"event stream refused: {exc}")
                    if exc.status in (401, 403):
                        _log("auth failure opening the stream; stopping")
                        break
                except Exception as exc:  # noqa: BLE001
                    _log(f"event stream dropped: {exc}")
                if self.stop_event.is_set():
                    break
                _log(f"reconnecting in {backoff:.0f}s…")
                self.stop_event.wait(backoff)
                backoff = min(backoff * 2, 30.0)
        finally:
            if self.heartbeat is not None:
                self.heartbeat.stop()

    def stop(self) -> None:
        self.stop_event.set()
        if self.heartbeat is not None:
            self.heartbeat.stop()
