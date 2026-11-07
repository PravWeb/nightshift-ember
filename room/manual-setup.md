# NightShift — manual setup (what the template cannot do)

`templates/nightshift.template.yaml` creates, in one run: the
`nightshift` room with its instructions, the `claude-reviewer` agent,
the `reviewer` (shared) and `release-manager` (exclusive) role
definitions, the `widgetapi` GitHub reference, the `release-notes-format`
seed document, and the kickoff message.

Everything below is real and necessary, but the v1 template grammar has
no way to express it — the official examples and `docs/TEMPLATES.md`
show no syntax for it — so it is done by hand / at runtime instead of
being faked in the YAML.

## 1. Put the demo repo on GitHub and fix the placeholder URL

The template grammar takes a literal URL for a created reference
(`value: {urls: [...]}`); it cannot create a GitHub repository or push
to one.

1. Create an empty repo named `widgetapi` on your GitHub account.
2. Push the seeded local repo to it:
   `cd project/demo-repo && git remote add origin https://github.com/PravWeb/widgetapi.git && git push -u origin main --tags`
   (that is this project's real repo; if you fork under a different
   account, substitute yours — keep the `v0.3` tag
   in the push — the demo reads the post-tag history).
3. In Switch Console, open the template and confirm
   `https://github.com/PravWeb/widgetapi` in **both** places —
   the reviewer's `repo:` and the room reference's `value.urls` — with
   the real URL, then run the template.

## 2. Ember joins the room itself

A template can only create Console/server-managed agents (`agents:`
entries with a provider, location, and directory). Ember is none of
those: it is a hand-coded agent that speaks the raw Switch agent
protocol, runs a local model, and registers itself
(`POST /agents/register-known`). No template syntax creates it — by
design; this is the project's "bring your own agent" beat.

Console / room steps after the template run:

1. Start Ember with the project's own CLI (see the project README /
   RUNBOOK): it registers with the server and connects to the room.
2. In the `nightshift` room, invite / add the registered `ember` agent
   if it did not join on connect (room members → add agent → `ember`).
3. Check `!roles`: `reviewer` should show the cloud reviewer once it
   has taken the role (step 3), `release-manager` unheld until the
   night shift.

## 3. Roles are taken at runtime, not assigned by the template

The template *defines* both roles in the room. The grammar has no field
for "agent X holds role Y on creation" — holding a role is a runtime
operation (`assume_role` / take-role op) an agent performs in the room.

Live steps:

1. Day shift: `claude-reviewer` takes the `reviewer` role when it starts
   work (or the human directs it: "@claude-reviewer take the reviewer
   job"). `!roles` confirms.
2. Night shift: the human says "@ember take the release-manager job and
   wrap the day." Ember takes the exclusive `release-manager` role,
   does the wrap, and `!roles` shows the mixed-vendor team.

## 4. The per-release notes document is created at wrap time

The template seeds only the *format* document (`release-notes-format`,
from `seed-document-release-notes.md`). Each actual release-notes
document ("v0.4 release notes") is created by Ember during the wrap,
via the protocol's document-creation op, filled from the room context
and the repo's post-tag git log. A template runs once at provisioning;
it cannot write a document whose content depends on the day's work.

## 5. First-run checks (2 minutes)

- Room `nightshift` exists, is private, and contains you and
  `claude-reviewer`.
- `!roles` lists `reviewer` (shared) and `release-manager` (exclusive).
- `!list-references` (or the room's references view) shows `widgetapi`
  pointing at the real GitHub URL from step 1 — not the placeholder.
- The kickoff message is in the room and the reviewer has replied in a
  thread with findings on the post-v0.3 auth fix.
- Ember appears as a room member after step 2; if it does not, the
  demo still runs with the reviewer + a human reading Ember's lines
  from the seeded notes, but say so plainly rather than faking it.
