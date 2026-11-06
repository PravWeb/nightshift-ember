"""Offline demo transcript — the demo backup path.

Runs the scripted brain through the NightShift demo scenario against an
in-process fake bridge (no network, no Switch server, no LLM), using the
real EmberAgent code paths: the same handle_message / do_wrap logic that
runs live. If EMBER_DEMO_REPO points at a real repo its git log is used;
otherwise a small throwaway repo is seeded in a temp dir so the wrap has
real commits to compose from.

    python3 -m ember simulate
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from .agent import EmberAgent
from .client import SwitchClient
from .config import Config


class FakeBridgeClient(SwitchClient):
    """A SwitchClient whose ops are answered in memory and recorded.

    Only the transport is faked: register/ops/stream plumbing is replaced
    with dict lookups, while EmberAgent above it runs unchanged."""

    def __init__(self, config: Config, context: dict):
        # Deliberately skip SwitchClient.__init__ (no state file, no HTTP).
        self.config = config
        self.base = "fake://offline"
        self.agent_id = "agent-ember-sim"
        self.api_key = "sim-key"
        self.connection_id = "sim-connection"
        self.cursor = 0
        self.generation = 1
        self._context = context
        self.ops: list[tuple[str, dict]] = []
        self.posted: list[str] = []

    def ensure_registered(self) -> None:  # already "registered"
        return None

    def call_op(self, name: str, args: dict | None = None) -> object:
        args = dict(args or {})
        self.ops.append((name, args))
        if name == "list_rooms":
            return [{"room_id": "room-nightshift", "name": "nightshift",
                     "description": "NightShift demo room", "connected": False,
                     "archived": False}]
        if name == "connect_to_room":
            return {"room_id": args.get("room_id"), "name": "nightshift"}
        if name == "list_roles":
            return [{"name": "reviewer", "exclusive": False,
                     "held_by": [{"name": "claude-reviewer"}]}]
        if name == "define_role":
            return {"status": "defined", "name": args.get("name")}
        if name == "assume_role":
            return {"role": args.get("role"), "instructions": "(simulated)"}
        if name == "read_context":
            return self._context
        if name == "create_room_document":
            return {"document_id": "doc-sim-1"}
        if name == "post_message":
            self.posted.append(args.get("body", ""))
            return {"event_id": f"evt-{len(self.posted)}"}
        return {"ok": True}


def _seed_temp_repo() -> str:
    tmp = Path(tempfile.mkdtemp(prefix="ember-sim-repo-"))

    def git(*args: str) -> None:
        subprocess.run(
            ["git", "-C", str(tmp), "-c", "user.name=Sim",
             "-c", "user.email=sim@example.invalid", *args],
            check=True, capture_output=True, text=True,
        )

    git("init")
    (tmp / "widgetapi.py").write_text('"""widgetapi v0.3"""\n', encoding="utf-8")
    git("add", ".")
    git("commit", "-m", "chore: initial widgetapi scaffold")
    git("tag", "v0.3")
    (tmp / "widgetapi.py").write_text(
        '"""widgetapi v0.4"""\n# auth + search\n', encoding="utf-8"
    )
    git("add", ".")
    git("commit", "-m", "feat: add widget search endpoint")
    git("add", ".")
    git("commit", "-m", "fix: repair auth token refresh", "--allow-empty")
    git("commit", "-m", "docs: document the v0.4 upgrade path", "--allow-empty")
    return str(tmp)


def _message_event(body: str, sender_name: str = "praveen",
                   message_id: str = "msg-sim") -> dict:
    return {
        "event": "message",
        "id": None,
        "data": {
            "type": "message",
            "room_id": "room-nightshift",
            "bridge_id": None,
            "channel_type": "channel_public",
            "payload": {
                "addressed": True,
                "sender": "@praveen:switch.local",
                "sender_name": sender_name,
                "message_id": message_id,
                "body": body,
                "timestamp": 0,
                "thread_id": None,
                "attachments": [],
            },
        },
    }


def run_simulation(config: Config | None = None) -> str:
    """Run the scenario and return the transcript text."""
    config = config or Config.from_env()
    config.brain = "scripted"  # simulation is deterministic by design
    if not config.demo_repo:
        config.demo_repo = _seed_temp_repo()

    context = {
        "threads": [
            {"root": {"id": "m1", "kind": "message", "sender": "u1",
                      "sender_name": "praveen",
                      "body": "v0.4 ships tomorrow. @claude-reviewer, review the auth PR. Ember takes release notes tonight.",
                      "timestamp": 1, "attachments": []},
             "replies": []},
            {"root": {"id": "m2", "kind": "message", "sender": "a2",
                      "sender_name": "claude-reviewer",
                      "body": "Review done: the auth fix looks right, but the token refresh test is still blocking v0.4 — it flakes on CI.",
                      "timestamp": 2, "attachments": []},
             "replies": []},
        ],
        "truncated": False,
        "oldest_timestamp": 1,
    }
    client = FakeBridgeClient(config, context)
    agent = EmberAgent(config, client)
    agent.startup_sequence()

    script = [
        "@ember take the release-manager job and wrap the day — !wrap",
        "@ember what's still blocking v0.4?",
    ]
    transcript: list[str] = [
        "#nightshift — NightShift simulation (scripted brain, fake bridge)",
        "",
        "praveen: v0.4 ships tomorrow. @claude-reviewer, review the auth PR. "
        "Ember takes release notes tonight.",
        "claude-reviewer: Review done: the auth fix looks right, but the "
        "token refresh test is still blocking v0.4 — it flakes on CI.",
        "",
    ]
    posted_before = 0
    for line in script:
        transcript.append(f"praveen: {line}")
        agent.handle_event(_message_event(line))
        for body in client.posted[posted_before:]:
            for chunk in body.splitlines():
                transcript.append(f"ember: {chunk}")
        posted_before = len(client.posted)
        transcript.append("")
    docs = [a for n, a in client.ops if n == "create_room_document"]
    for doc in docs:
        transcript.append(f"[room document created: {doc['name']!r}]")
    transcript.append("[ops called: "
                      + ", ".join(n for n, _ in client.ops) + "]")
    return "\n".join(transcript)
