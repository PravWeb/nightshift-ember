"""Ember configuration — everything comes from the environment.

No third-party dotenv: ``load_dotenv`` below is a tiny parser for the
``.env`` file next to the working directory, used only by the CLI entry
point. Tests construct :class:`Config` directly.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _env(name: str, default: str = "") -> str:
    value = os.environ.get(name)
    return default if value is None else value.strip()


@dataclass
class Config:
    """Runtime configuration for one Ember process."""

    # Switch Agent Bridge base URL (NOT the Gateway URL — see the protocol
    # doc's "Finding the bridge base URL"; probe it with GET /health).
    server_url: str = "http://localhost:8000"
    # Registration token: authenticates registration exactly once. It is
    # rejected everywhere else; the agent API key is what opens streams.
    registration_token: str = ""
    # Local LLM (OpenAI-compatible). Defaults target a local llama.cpp
    # server; nothing here ever points at a cloud endpoint by default.
    llm_base_url: str = "http://localhost:8080/v1"
    llm_model: str = "local"
    # Registered agent name (must match ^[a-z0-9][a-z0-9._-]*$).
    name: str = "ember"
    # Room role to define (if missing) and assume on startup.
    role: str = "release-manager"
    # Instructions handed to define_role for the role above.
    role_instructions: str = (
        "Own the release wrap: read the room context and the demo repo's "
        "git log, publish the release notes as a room document, post the "
        "wrap summary in chat, and flag anything still blocking the "
        "release. Runs on a local model; spends no cloud tokens."
    )
    # Path to the git repo the wrap tool reads (EMBER_DEMO_REPO).
    demo_repo: str = ""
    # Release the wrap is for (document name is f"{release} release notes").
    release: str = "v0.4"
    # "llm" (default) or "scripted" (deterministic, no LLM call at all).
    brain: str = "llm"
    # agent_type sent to POST /agents/register-known. Switch only accepts
    # its known provider types here (claude-code, codex, opencode,
    # antigravity, cursor — see core/switch_core/gateway/known_agents.py);
    # "codex" resolves to the generic profile. If the server rejects the
    # type (400), Ember falls back to the lower-level POST /agents with a
    # full always_on integration profile, which is the door the protocol
    # doc reserves for agents that are not a known CLI.
    agent_type: str = "codex"
    # Optional: pin Ember to one room id instead of the first listed room.
    room_id: str = ""
    # Where the one-time API key + agent id + connection id persist.
    state_file: str = ".ember-state.json"
    # Heartbeat cadence. The protocol says beat every 2 s (TTL 6 s).
    heartbeat_seconds: float = 2.0
    # Extra environment passthrough kept for debugging.
    extra: dict = field(default_factory=dict)

    @classmethod
    def from_env(cls, environ: dict | None = None) -> "Config":
        env = os.environ if environ is None else environ

        def get(name: str, default: str) -> str:
            value = env.get(name)
            return default if value is None or value.strip() == "" else value.strip()

        heartbeat = get("EMBER_HEARTBEAT_SECONDS", "2")
        try:
            heartbeat_seconds = float(heartbeat)
        except ValueError:
            heartbeat_seconds = 2.0
        return cls(
            server_url=get("EMBER_SERVER_URL", "http://localhost:8000").rstrip("/"),
            registration_token=get("EMBER_REGISTRATION_TOKEN", ""),
            llm_base_url=get("EMBER_LLM_BASE_URL", "http://localhost:8080/v1").rstrip("/"),
            llm_model=get("EMBER_LLM_MODEL", "local"),
            name=get("EMBER_NAME", "ember"),
            role=get("EMBER_ROLE", "release-manager"),
            demo_repo=get("EMBER_DEMO_REPO", ""),
            release=get("EMBER_RELEASE", "v0.4"),
            brain=get("EMBER_BRAIN", "llm").lower(),
            agent_type=get("EMBER_AGENT_TYPE", "codex"),
            room_id=get("EMBER_ROOM_ID", ""),
            state_file=get("EMBER_STATE_FILE", ".ember-state.json"),
            heartbeat_seconds=heartbeat_seconds,
        )

    @property
    def state_path(self) -> Path:
        return Path(self.state_file)


def load_dotenv(path: str | Path = ".env") -> None:
    """Minimal .env loader (KEY=value lines, # comments). Never overrides
    variables already present in the real environment."""
    p = Path(path)
    if not p.is_file():
        return
    for raw in p.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value
