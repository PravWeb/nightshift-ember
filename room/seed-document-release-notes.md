# Seed document: release notes format

The format Ember's wrap document follows. Ember (release manager)
creates one room document per release in this shape — in the demo,
"v0.4 release notes". In the template this seed is carried as an entry
under the room's `docs:`, so the format is in the room from the moment
it is created.

Copy the structure exactly. Fill every section; write "None." in a
section that is genuinely empty rather than deleting the section.

---

# v0.4 release notes

## Merged

- One line per change that merged in the period, with its commit
  subject and short hash, e.g.:
  `- fix: reject expired tokens in auth check (a1b2c3d)`
- Group nothing, reorder nothing: git-log order, newest first.

## Blocked

- One line per blocked item: what it is, what it waits on, and who can
  unblock it, e.g.:
  `- Release sign-off — waiting on reviewer re-check of the auth fix.`
- A blocker with no named owner is written as "owner: unassigned" —
  never omitted.

## Next

- One line per next step, in the order the team should take them:
  the first thing tomorrow, then the rest of the release checklist.

## Cost

Night shift complete. Cloud tokens spent tonight: 0.

---

Rules for the document:

- Every Merged line must exist in the git log for the period (since the
  last release tag). If it is not in the log, it does not go in.
- Every Blocked line must come from the room: a thread, a review
  finding, or a message that names the blocker.
- The cost line is always the last line, worded exactly as above. It is
  the receipt for the night shift: the wrap ran on a local model, so
  the cloud-token count for it is 0.
