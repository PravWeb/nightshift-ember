# NightShift Demo — 4-minute shot-by-shot script

The demo is a story with a clock: **day shift → hand-off → night shift → morning brief**. Everything happens in one place — the `#nightshift` room in Mattermost — so the recording is one screen, one room, and a team changing shifts in front of the camera.

Total runtime: ~4 minutes. One narrator (the human in the room). No cuts inside a beat if you can avoid them — the chat *is* the footage.

---

## Pre-flight checklist

Run through this before you press record:

- [ ] Switch Console is open, and your local Switch server is up (bundled Mattermost reachable).
- [ ] The `#nightshift` room is open in Mattermost, full-screen, with the member list visible or one click away.
- [ ] **Roles are unheld at the start, as the script expects:** `!roles` shows **reviewer** held by claude-reviewer and **release-manager** unheld. If Ember already holds release-manager from a rehearsal, have Ember release it (or restart Ember) so Beat 3's role-taking happens on camera.
- [ ] claude-reviewer is in the room, signed in via Console, and idle (not busy in another room — an agent's session works in one room at a time).
- [ ] Ember is running (`python3 -m ember run`), registered, a member of `#nightshift`, and permitted to answer you in this room — but has **not** yet been asked to wrap.
- [ ] llama-server is warm: `llama-server --model <path-to-a-small-GGUF> --port 8080` has loaded the model and answered at least one test request, so Beat 3 doesn't wait on a cold load. (Or `EMBER_BRAIN=scripted` is set, if you're recording with the scripted brain.)
- [ ] The demo repo is ready: `demo-repo/` (widgetapi) is in place with its seeded history and v0.3 tag — pushed to GitHub if the room's reference points at the hosted repo, or local if your setup reads it locally. The auth fix the reviewer will discuss is in the history.
- [ ] Font size up, notifications off, terminal with Ember's log visible in a second window or tab for the Beat 3 cutaway.
- [ ] A second `!roles` is your closing shot — know where the room's document list is, too, so Beat 4 can show the release-notes document in place.

---

## Beat 1 — The room, and the empty chair (0:00–0:40)

**On screen:** The `#nightshift` room in Mattermost. Member list shows you, claude-reviewer, and Ember. The room instructions are visible or scrolled past: this is the release room for widgetapi.

**You type (exactly):**

```
!roles
```

**What replies (shape):** The room's role list: **reviewer** — held by claude-reviewer (shared role). **release-manager** — *unheld* (exclusive role). That empty chair is the setup for the whole demo.

**You type (exactly):**

```
v0.4 ships tomorrow. @claude-reviewer, review the auth PR. Ember takes release notes tonight.
```

**What replies (shape):** claude-reviewer acknowledges and starts the review. Ember says nothing — it wasn't addressed, and agents act on messages that address them. That silence is deliberate; narrate it.

**Camera/screen notes:** Start wide on the room so the member list and both agent names are readable. Narrate the premise in one breath: *"Day shift is a cloud agent. Night shift is Ember — a local-model agent we wrote, running on this machine's GPU. Watch who holds which job."* Hold on the `!roles` output for two beats before typing the kickoff line.

---

## Beat 2 — Day shift: the cloud reviewer works (0:40–1:40)

**On screen:** The same room. claude-reviewer posts its review in the auth PR thread.

**You type:** Nothing new in this beat — the kickoff message from Beat 1 is the instruction. If the reviewer needs a nudge, address it again by its exact name: `@claude-reviewer ?`

**What replies (shape):** claude-reviewer's findings, grounded via the room's GitHub reference to `widgetapi`: a short review of the auth change — what the change does, what looks right, and the findings that matter for v0.4 (the seeded issue in the auth fix among them). Findings land in the thread, in the room, where the whole team — including Ember, later — can read them.

**Camera/screen notes:** Let the reviewer's message stream in; don't talk over it. Scroll the thread once, slowly, so the findings are legible. Narrate the cost contrast lightly: *"This is the work a frontier model is good at — judgement on a diff. It costs cloud tokens, and during the day, that's the right spend."* End the beat on the reviewer's final finding — Ember will need it in Beat 4.

---

## Beat 3 — The hand-off: Ember takes the night shift (1:40–2:50)

**On screen:** The same room. This is the centrepiece — keep the camera on the chat.

**You type (exactly):**

```
@ember take the release-manager job and wrap the day
```

**What replies (shape):**

1. Ember takes the exclusive **release-manager** role through a Switch role operation — the role's instructions arrive with the job.
2. Ember reads the room's context (`read_context`): the kickoff, the reviewer's findings, the day's decisions.
3. Ember reads the `widgetapi` git log on the local machine and composes the wrap.
4. Ember creates the room document **"v0.4 release notes"**.
5. Ember posts the wrap in chat: what merged, what's blocked (the reviewer's open finding, flagged), and what's next before v0.4 ships.

**Camera/screen notes:** Type the hand-off message and then *stop touching anything*. Let Ember's steps land one by one. If you have a second window, cut briefly to Ember's terminal log as it works — registration held, heartbeat running, ops going out — then back to the room for the wrap post. Narrate the one fact that matters: *"Ember is not a Console agent and there's no SDK. It's a Python program — standard library only — speaking the Switch agent protocol itself, and its model is llama.cpp on this machine's GPU."* When the wrap post lands, scroll it once so "what's blocked" is on screen — Beat 4 quotes it.

---

## Beat 4 — Morning brief: ask the document (2:50–3:30)

**On screen:** The same room, next "morning". If your room UI shows documents, open the room's document list first and show **"v0.4 release notes"** sitting there — the night shift's deliverable, in the room, not buried in scrollback.

**You type (exactly):**

```
@ember what's still blocking v0.4?
```

**What replies (shape):** Ember answers in the room, in-thread, from the release-notes document and the room context: the blockers it flagged in the wrap — led by the reviewer's open auth finding — stated plainly, with what's needed to clear them. No new model spend beyond the local one, no re-reading the repo from a cloud service: the answer comes from the work the night shift already did.

**Camera/screen notes:** Keep it conversational and quick — this beat sells "the wrap is usable, not just produced." Narrate: *"I didn't brief Ember this morning. The document briefed both of us."* If the answer threads under your question, keep the thread open on screen.

---

## Beat 5 — Closing shot: the team, and the bill (3:30–4:00)

**On screen:** The room, one last time.

**You type (exactly):**

```
!roles
```

**What replies (shape):** The role list, now full: **reviewer** — claude-reviewer. **release-manager** — ember. A mixed-vendor, mixed-cost team in one room: a cloud Claude agent and a local-model agent, holding different jobs, sharing one context.

Then Ember's closing line lands (its wrap sign-off, in the room):

> **"Night shift complete. Cloud tokens spent tonight: 0."**

**Camera/screen notes:** Hold the final frame on `!roles` with Ember's line visible. Narrate the close in one line: *"Your agents don't all have to be cloud agents. Give the night shift to one that runs on your own machine."* End on the room — no logo card, no cutaway. The room is the product shot.

---

## Plan B — if live Ember fails during recording

Run the same flow in simulation and narrate over it:

```bash
python3 -m ember simulate
```

Put the simulation transcript on screen and walk the same five beats against it. The workflow is identical — same hand-off, same role-taking, same wrap, same document, same morning answer — with the transport simulated instead of live. Fix the live path afterwards using the troubleshooting table in [RUNBOOK.md](RUNBOOK.md) (Console open? Ember permitted in the room and addressed by its exact name? llama-server up on port 8080, or the scripted brain as the fallback?), then re-record Beats 3–5 live when Ember is answering.
