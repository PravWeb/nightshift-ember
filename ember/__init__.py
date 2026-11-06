"""Ember — a hand-coded Switch agent speaking the raw agent protocol.

Stdlib-only (Python 3.11+). Implements the wire protocol documented in
``docs/official/internals/agent-protocol.md`` of the Switch repo:

* registration via ``POST /agents/register-known`` (API key returned once,
  persisted to a local state file),
* one SSE stream down (``GET /agents/{id}/events``),
* HTTP operations up (``GET /agents/{id}/ops``,
  ``POST /agents/{id}/ops/{operation}``),
* a connection heartbeat (``POST /agents/{id}/connection/beat``) every 2 s.

The brain is an OpenAI-compatible chat call to a *local* LLM server
(llama.cpp by default) with a deterministic scripted fallback, so Ember
runs — and its tests pass — with no cloud model involved at all.
"""

__version__ = "0.4.0"

__all__ = ["__version__"]
