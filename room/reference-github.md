# Reference: widgetapi (GitHub)

What the `widgetapi` GitHub reference attached to the `nightshift` room
is for, and when to consult it. In the template this is the entry under
the room's `references:` with `type: github`.

- **Name:** widgetapi
- **Type:** github
- **URL:** `https://github.com/PravWeb/widgetapi` — the demo repo,
  pushed to GitHub from the seeded source in `project/demo-repo/`
  (see `manual-setup.md`).

---

## What it is

The single source of truth for the code this room ships: the `widgetapi`
repository — a tiny Python package with a framework-free API sketch, a
token auth module, and its tests. Its git history (the `v0.3` tag and
the commits after it) is what the demo reviews and what the nightly wrap
is written from.

## When to consult it

- **Reviewer:** before posting any finding. Read the diff under review,
  the files it touches, and the surrounding code in the reference. A
  finding that does not name a file in this repo is not grounded.
- **Release manager (Ember):** when composing the wrap, for the commit
  list since the last tag. Ember reads its local clone's git log; the
  reference is how everyone else in the room sees the same history.
- **Anyone answering a code question in this room:** check the reference
  first. If the answer is not in the repo, say so — do not answer from
  memory of similar projects.

## What it is not for

- It grants no write access by itself. Reviewers read and comment in the
  room; they do not push to the repo from the reference.
- It is not a substitute for running the tests. Cite the test output you
  actually ran, not the fact that tests exist in the reference.
