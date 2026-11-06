"""Ember's brain: a local LLM when reachable, a scripted brain otherwise.

``llm_brain`` POSTs to an OpenAI-compatible ``/chat/completions`` endpoint
(``EMBER_LLM_BASE_URL``, default a local llama.cpp server). Any failure —
connection refused, timeout, malformed response — falls back to
``scripted_brain``, a deterministic responder, so Ember never goes silent
in the room. ``EMBER_BRAIN=scripted`` skips the LLM entirely (tests and
the demo backup path use it).
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

SYSTEM_PROMPT = (
    "You are Ember, the night-shift release-manager agent in a Switch room. "
    "You run on a local model on the team's own machine; you spend no cloud "
    "tokens. Answer briefly and concretely from the room context you are "
    "given. If asked what is blocking the release, only name blockers that "
    "appear in the context. Never invent commits, people, or status."
)


def flatten_context(context: dict | None) -> list[dict]:
    """Flatten a read_context result ({threads:[{root, replies}]}) into a
    chronological-ish list of {sender_name, body, id} entries. Also accepts
    a flat {"messages": [...]} shape defensively."""
    if not isinstance(context, dict):
        return []
    entries: list[dict] = []
    threads = context.get("threads")
    if isinstance(threads, list):
        for thread in threads:
            if not isinstance(thread, dict):
                continue
            root = thread.get("root")
            if isinstance(root, dict):
                entries.append(root)
            for reply in thread.get("replies") or []:
                if isinstance(reply, dict):
                    entries.append(reply)
    for key in ("messages", "entries"):
        flat = context.get(key)
        if isinstance(flat, list):
            entries.extend(e for e in flat if isinstance(e, dict))
    return entries


def format_context(entries: list[dict], limit: int = 30) -> str:
    lines = []
    for entry in entries[-limit:]:
        sender = entry.get("sender_name") or entry.get("sender") or "?"
        body = (entry.get("body") or "").strip()
        if body:
            lines.append(f"{sender}: {body}")
    return "\n".join(lines)


# ── Scripted brain (deterministic) ──────────────────────────────────────────


def scripted_brain(user_text: str, context: dict | None = None) -> str:
    """Deterministic replies, no model involved. Used as the fallback and
    as the brain in tests / simulate mode."""
    from .tools import extract_blockers

    text = (user_text or "").lower()
    entries = flatten_context(context)
    if "block" in text:
        blockers = extract_blockers(entries)
        if blockers:
            listed = "; ".join(blockers)
            return (
                f"Still blocking the release, from the room context: {listed}. "
                "Cloud tokens spent tonight: 0."
            )
        return (
            "Nothing in the room context is flagged as blocking the release. "
            "Cloud tokens spent tonight: 0."
        )
    if "status" in text or "how" in text:
        return (
            f"NightShift status: I'm Ember, holding the release-manager role "
            f"on the night shift. I can see {len(entries)} message(s) of room "
            "context. Ask me to !wrap and I'll publish the release notes as a "
            "room document. Cloud tokens spent tonight: 0."
        )
    if "role" in text:
        return (
            "I'm holding the release-manager role for tonight's wrap. "
            "Cloud tokens spent tonight: 0."
        )
    return (
        "Got it — noted for the night shift. Ask me to !wrap and I'll "
        "publish the release notes as a room document. "
        "Cloud tokens spent tonight: 0."
    )


# ── LLM brain (OpenAI-compatible, local) ────────────────────────────────────


def llm_brain(
    user_text: str,
    context: dict | None = None,
    *,
    base_url: str,
    model: str,
    timeout: float = 30.0,
) -> str:
    """One chat completion against the local LLM server.

    Raises on any transport or shape problem; callers fall back."""
    entries = flatten_context(context)
    transcript = format_context(entries)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if transcript:
        messages.append(
            {
                "role": "system",
                "content": f"Recent room context:\n{transcript}",
            }
        )
    messages.append({"role": "user", "content": user_text})
    payload = json.dumps(
        {"model": model, "messages": messages, "temperature": 0.3}
    ).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/chat/completions",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = json.loads(response.read().decode("utf-8"))
    content = data["choices"][0]["message"]["content"]
    if not isinstance(content, str) or not content.strip():
        raise ValueError("LLM returned an empty completion")
    return content.strip()


def get_reply(
    user_text: str,
    context: dict | None = None,
    *,
    brain_mode: str = "llm",
    llm_base_url: str = "http://localhost:8080/v1",
    llm_model: str = "local",
) -> str:
    """The brain entry point: LLM first (unless scripted), scripted on any
    failure. Never raises for an unreachable LLM."""
    if brain_mode == "scripted":
        return scripted_brain(user_text, context)
    try:
        return llm_brain(
            user_text,
            context,
            base_url=llm_base_url,
            model=llm_model,
        )
    except Exception as exc:  # noqa: BLE001 — fallback is the whole point
        print(f"[ember] LLM brain failed ({exc}); using scripted brain",
              file=sys.stderr)
        return scripted_brain(user_text, context)
