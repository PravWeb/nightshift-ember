"""Ember test suite — stdlib unittest, localhost only, no pip installs.

Run from the project root:

    python3 -m unittest discover -s tests -v

The integration tests drive the real EmberAgent + SwitchClient over HTTP
against tests/mock_bridge.py, a mock Agent Bridge implementing the
documented protocol. Tool/brain tests are pure unit tests (the git tests
seed a throwaway repo in a temp dir).
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from ember import brain as brain_module  # noqa: E402
from ember.agent import EmberAgent  # noqa: E402
from ember.client import HeartbeatThread, SwitchClient  # noqa: E402
from ember.config import Config  # noqa: E402
from ember.tools import compose_release_notes, git_log, latest_tag  # noqa: E402
from mock_bridge import API_KEY, AGENT_ID, REG_TOKEN, start_mock  # noqa: E402

SEED_COMMITS = [
    "feat: add widget search endpoint",
    "fix: repair auth token refresh",
    "docs: document the v0.4 upgrade path",
]


def seed_repo(path: Path) -> Path:
    """A tiny git repo: one scaffold commit tagged v0.3, then SEED_COMMITS."""
    path.mkdir(parents=True, exist_ok=True)

    def git(*args: str) -> None:
        subprocess.run(
            ["git", "-C", str(path), "-c", "user.name=Test",
             "-c", "user.email=test@example.invalid", *args],
            check=True, capture_output=True, text=True,
        )

    git("init")
    (path / "widgetapi.py").write_text('"""widgetapi"""\n', encoding="utf-8")
    git("add", ".")
    git("commit", "-m", "chore: initial widgetapi scaffold")
    git("tag", "v0.3")
    for subject in SEED_COMMITS:
        git("commit", "-m", subject, "--allow-empty")
    return path


def wait_for(predicate, timeout: float = 8.0, interval: float = 0.05) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


class BridgeTestCase(unittest.TestCase):
    mention_body = "@ember what's the status?"

    def setUp(self):
        self.bridge = start_mock(mention_body=self.mention_body)
        self.tmp = tempfile.TemporaryDirectory()
        tmp = Path(self.tmp.name)
        self.state_file = tmp / ".ember-state.json"
        self.repo = seed_repo(tmp / "demo-repo")
        self.config = Config(
            server_url=self.bridge.url,
            registration_token=REG_TOKEN,
            name="ember",
            role="release-manager",
            demo_repo=str(self.repo),
            brain="scripted",
            state_file=str(self.state_file),
            heartbeat_seconds=0.05,
        )
        self.client = SwitchClient(self.config)

    def tearDown(self):
        self.bridge.shutdown()
        self.bridge.server_close()
        self.tmp.cleanup()


class RegistrationTests(BridgeTestCase):
    def test_registration_persists_key(self):
        result = self.client.register()
        self.assertEqual(result["id"], AGENT_ID)
        self.assertEqual(result["api_key"], API_KEY)
        # The one-time key must be on disk, with the agent id + connection id.
        self.assertTrue(self.state_file.is_file())
        state = json.loads(self.state_file.read_text(encoding="utf-8"))
        self.assertEqual(state["api_key"], API_KEY)
        self.assertEqual(state["agent_id"], AGENT_ID)
        self.assertTrue(state["connection_id"])
        # The bridge saw a register-known call with the right name.
        regs = self.bridge.registrations
        self.assertEqual(len(regs), 1)
        self.assertEqual(regs[0]["path"], "/agents/register-known")
        self.assertEqual(regs[0]["body"]["name"], "ember")
        # A fresh client over the same state file is already registered.
        reloaded = SwitchClient(self.config)
        self.assertTrue(reloaded.registered)
        self.assertEqual(reloaded.api_key, API_KEY)

    def test_ops_discovery(self):
        self.client.register()
        ops = self.client.list_ops()
        for name in ("post_message", "read_context", "define_role",
                     "assume_role", "create_room_document"):
            self.assertIn(name, ops)


class HeartbeatTests(BridgeTestCase):
    def test_heartbeat_fires(self):
        self.client.register()
        self.client.ensure_connection_id()
        heartbeat = HeartbeatThread(self.client, interval=0.05)
        heartbeat.start()
        try:
            self.assertTrue(
                wait_for(lambda: len(self.bridge.beats) >= 3, timeout=5),
                f"expected >=3 beats, got {len(self.bridge.beats)}",
            )
        finally:
            heartbeat.stop()
            heartbeat.join(timeout=2)
        for beat in self.bridge.beats:
            self.assertEqual(beat["connection_id"],
                             self.client.connection_id)


class MentionFlowTests(BridgeTestCase):
    mention_body = "@ember what's the status?"

    def test_mention_triggers_context_read_and_reply(self):
        agent = EmberAgent(self.config, self.client)
        thread = threading.Thread(target=agent.run_forever, daemon=True)
        thread.start()
        try:
            ok = wait_for(lambda: bool(self.bridge.ops_named("post_message")))
            self.assertTrue(ok, f"no post_message; ops={self.bridge.ops_calls}")
        finally:
            agent.stop()
            thread.join(timeout=3)
        ops = self.bridge.ops_calls
        names = [c["operation"] for c in ops]
        # Startup claimed the room and took the role before replying.
        self.assertIn("connect_to_room", names)
        self.assertIn("define_role", names)
        self.assertIn("assume_role", names)
        # read_context happened before the reply.
        self.assertLess(names.index("read_context"),
                        names.index("post_message"))
        reply = self.bridge.ops_named("post_message")[0]["args"]
        self.assertIn("release-manager", reply["body"])
        self.assertIn("Cloud tokens spent tonight: 0.", reply["body"])
        # Threaded reply: thread_id is the mentioning message's id.
        self.assertEqual(reply["thread_id"], "msg-mention-1")
        # Ops carried the connection id header, per the protocol.
        self.assertTrue(
            all(c["connection_id"] for c in ops),
            f"ops missing connection header: {ops}",
        )


class WrapTests(BridgeTestCase):
    def _wrap_event(self, body: str) -> dict:
        return {
            "type": "message",
            "room_id": "room-nightshift",
            "payload": {
                "addressed": True,
                "sender": "@alice:switch.local",
                "sender_name": "alice",
                "message_id": "msg-wrap-1",
                "body": body,
                "timestamp": 3,
                "thread_id": None,
                "attachments": [],
            },
        }

    def test_wrap_creates_document_and_posts_summary(self):
        self.client.register()
        agent = EmberAgent(self.config, self.client)
        agent.handle_message(self._wrap_event("@ember please !wrap the day"))
        docs = self.bridge.ops_named("create_room_document")
        self.assertEqual(len(docs), 1)
        doc = docs[0]["args"]
        self.assertEqual(doc["name"], "v0.4 release notes")
        for subject in SEED_COMMITS:
            self.assertIn(subject, doc["content"])
        posts = self.bridge.ops_named("post_message")
        self.assertEqual(len(posts), 1)
        body = posts[0]["args"]["body"]
        for subject in SEED_COMMITS:
            self.assertIn(subject, body)
        self.assertTrue(
            body.rstrip().endswith("Cloud tokens spent tonight: 0."),
            f"wrap summary must end with the zero-tokens line:\n{body}",
        )
        # The blocker from the mock room context is surfaced.
        self.assertIn("blocking v0.4", body)

    def test_wrap_word_also_triggers(self):
        self.client.register()
        agent = EmberAgent(self.config, self.client)
        agent.handle_message(
            self._wrap_event("@ember can you wrap the day for us?")
        )
        self.assertEqual(len(self.bridge.ops_named("create_room_document")), 1)


class GitLogToolTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = seed_repo(Path(self.tmp.name) / "repo")

    def tearDown(self):
        self.tmp.cleanup()

    def test_git_log_since_tag(self):
        self.assertEqual(latest_tag(self.repo), "v0.3")
        commits = git_log(self.repo, since_tag="v0.3")
        self.assertEqual([c["subject"] for c in commits],
                         list(reversed(SEED_COMMITS)))
        for commit in commits:
            self.assertEqual(len(commit["short_hash"]), 7)
            self.assertTrue(commit["hash"].startswith(commit["short_hash"]))

    def test_git_log_full_history_and_unknown_tag(self):
        commits = git_log(self.repo)
        self.assertEqual(len(commits), len(SEED_COMMITS) + 1)
        # An unknown tag falls back to full history instead of failing.
        self.assertEqual(git_log(self.repo, since_tag="v9.9"), commits)

    def test_release_notes_grouping(self):
        commits = git_log(self.repo, since_tag="v0.3")
        notes = compose_release_notes(commits, version="v0.4",
                                      since_tag="v0.3")
        self.assertIn("# v0.4 release notes", notes)
        self.assertIn("## Features", notes)
        self.assertIn("## Fixes", notes)
        self.assertIn("## Documentation", notes)
        self.assertIn("feat: add widget search endpoint", notes)


class BrainFallbackTests(unittest.TestCase):
    def test_llm_failure_falls_back_to_scripted(self):
        # Port 1 on localhost: nothing listens, connection refused fast.
        reply = brain_module.get_reply(
            "what's the status?",
            {"threads": []},
            brain_mode="llm",
            llm_base_url="http://127.0.0.1:1/v1",
            llm_model="local",
        )
        self.assertIn("release-manager", reply)
        self.assertIn("Cloud tokens spent tonight: 0.", reply)

    def test_scripted_brain_answers_blocker_question(self):
        context = {
            "threads": [
                {"root": {"id": "m9", "kind": "message", "sender": "x",
                          "sender_name": "bob",
                          "body": "The payment test is blocking v0.4.",
                          "timestamp": 1, "attachments": []},
                 "replies": []}
            ]
        }
        reply = brain_module.scripted_brain("what's still blocking v0.4?",
                                            context)
        self.assertIn("payment test is blocking", reply)


if __name__ == "__main__":
    unittest.main()
