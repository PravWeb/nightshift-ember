"""Ember's local tools: a read-only git-log reader and a release-notes
composer. Pure stdlib; git is invoked with subprocess and never writes.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

_FIELD = "\x1f"   # unit separator between fields of one commit
_RECORD = "\x1e"  # record separator between commits


def _git(path: str, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(path), *args],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    if result.returncode != 0:
        raise ValueError(
            f"git {' '.join(args)} failed in {path}: {result.stderr.strip()}"
        )
    return result.stdout


def git_tags(path: str | Path) -> list[str]:
    """Tags in the repo, newest first (by version, then creation date)."""
    out = _git(str(path), "tag", "--sort=-v:refname")
    return [line.strip() for line in out.splitlines() if line.strip()]


def latest_tag(path: str | Path) -> str | None:
    tags = git_tags(path)
    return tags[0] if tags else None


def _tag_exists(path: str, tag: str) -> bool:
    result = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "--verify", f"refs/tags/{tag}"],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    return result.returncode == 0


def git_log(
    path: str | Path,
    since_tag: str | None = None,
    limit: int = 100,
) -> list[dict]:
    """Commits in ``path``, newest first.

    Each entry is ``{"hash", "short_hash", "subject", "author", "date"}``.
    When ``since_tag`` names an existing tag, only commits in
    ``<tag>..HEAD`` are returned; an unknown tag falls back to the full
    (limited) history rather than failing the wrap.
    """
    repo = str(path)
    if not Path(repo).exists():
        raise ValueError(f"demo repo path does not exist: {repo}")
    rev_range = "HEAD"
    if since_tag and _tag_exists(repo, since_tag):
        rev_range = f"{since_tag}..HEAD"
    fmt = _FIELD.join(["%H", "%s", "%an", "%ad"]) + _RECORD
    out = _git(
        repo,
        "log",
        rev_range,
        f"--max-count={int(limit)}",
        "--date=short",
        f"--pretty=format:{fmt}",
    )
    commits: list[dict] = []
    for record in out.split(_RECORD):
        record = record.strip("\n")
        if not record.strip():
            continue
        parts = record.split(_FIELD)
        if len(parts) != 4:
            continue
        full_hash, subject, author, date = (p.strip() for p in parts)
        commits.append(
            {
                "hash": full_hash,
                "short_hash": full_hash[:7],
                "subject": subject,
                "author": author,
                "date": date,
            }
        )
    return commits


# Conventional-commit prefix -> release-notes section, in display order.
_SECTIONS: list[tuple[str, tuple[str, ...]]] = [
    ("Features", ("feat", "feature")),
    ("Fixes", ("fix", "bugfix", "hotfix")),
    ("Documentation", ("docs", "doc")),
    ("Maintenance", ("chore", "refactor", "test", "tests", "perf", "style", "build", "ci")),
]
_FALLBACK_SECTION = "Other changes"


def _section_for(subject: str) -> str:
    prefix = subject.split(":", 1)[0].split("(", 1)[0].strip().lower()
    for name, prefixes in _SECTIONS:
        if prefix in prefixes:
            return name
    return _FALLBACK_SECTION


def compose_release_notes(
    commits: list[dict],
    version: str = "v0.4",
    since_tag: str | None = None,
    blockers: list[str] | None = None,
) -> str:
    """Markdown release notes: commits grouped by conventional type."""
    lines: list[str] = [f"# {version} release notes", ""]
    if since_tag:
        lines.append(f"Changes since {since_tag}.")
        lines.append("")
    if not commits:
        lines.append("_No commits since the last tag._")
        lines.append("")
    grouped: dict[str, list[dict]] = {}
    for commit in commits:
        grouped.setdefault(_section_for(commit["subject"]), []).append(commit)
    order = [name for name, _ in _SECTIONS] + [_FALLBACK_SECTION]
    for section in order:
        entries = grouped.get(section)
        if not entries:
            continue
        lines.append(f"## {section}")
        lines.append("")
        for commit in entries:
            lines.append(f"- {commit['subject']} (`{commit['short_hash']}`)")
        lines.append("")
    if blockers:
        lines.append("## Still blocking")
        lines.append("")
        for blocker in blockers:
            lines.append(f"- {blocker}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def compose_wrap_summary(
    commits: list[dict],
    version: str = "v0.4",
    blockers: list[str] | None = None,
    document_name: str | None = None,
) -> str:
    """The chat wrap message. Always ends with the zero-cloud-tokens line."""
    lines: list[str] = [f"Night shift wrap — {version}:"]
    if commits:
        lines.append(f"{len(commits)} commit(s) wrapped:")
        for commit in commits:
            lines.append(f"- {commit['subject']} (`{commit['short_hash']}`)")
    else:
        lines.append("No new commits since the last tag.")
    if blockers:
        lines.append("Still blocking:")
        for blocker in blockers:
            lines.append(f"- {blocker}")
    else:
        lines.append("Nothing in the room context is flagged as blocking.")
    if document_name:
        lines.append(f"Full notes published as the room document \"{document_name}\".")
    lines.append("Night shift complete.")
    lines.append("Cloud tokens spent tonight: 0.")
    return "\n".join(lines)


def extract_blockers(
    context_entries: list[dict], own_name: str = "ember"
) -> list[str]:
    """Room-context entries that read as blockers (body mentions blocking).

    Two exclusions, both learned live (2026-11-06): the agent's OWN posts
    — its wrap summary and its answers quote the blocker list, so without
    this the notes cite themselves as a blocker — and messages addressed
    TO the agent (a question about blockers is not itself a blocker).
    """
    blockers: list[str] = []
    for entry in context_entries:
        body = (entry.get("body") or "").strip()
        lowered = body.lower()
        sender = (entry.get("sender_name") or "").strip().lower()
        if sender == own_name.lower():
            continue
        if lowered.startswith(f"@{own_name.lower()}"):
            continue
        if "block" in lowered and body not in blockers:
            blockers.append(body)
    return blockers
