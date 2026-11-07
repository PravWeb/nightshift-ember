# NightShift Runbook — your live path, in about 30 minutes

> ## ✅ LIVE STATUS — already running on the PC (verified Fri 2026-11-06 night)
>
> The full stack below was stood up headlessly on the PC and **Ember has
> already completed the whole demo flow against the real server** (role
> assumed, wrap posted, release-notes document created, follow-up answered
> by the local model). Evidence: `~/workspace/switch-hackathon/live-run/`
> (transcript + document + logs) and `LIVE-RUN-REPORT.md` in
> `~/workspace/switch-hackathon/`.
>
> **What is running on the PC right now** (all under `~/switch-hackathon/`):
> - Switch stack (Docker): `cd ~/switch-hackathon/stack && docker compose -f standalone-docker-compose.yml -p switch --profile collab --profile gateway ps` — switch-core 0.31.0 on :8000, Gateway on :3000, Mattermost on :8065, Postgres. Health: `curl localhost:8000/health`.
> - Room `nightshift` (id `76bdfa2f-42ac-4cc0-96df-e549b1f27a47`), Mattermost channel `#nightshift` in team `switch`. Seeded Mattermost user: `user` (password in `~/switch-hackathon/stack/.env` → `MATTERMOST_USER_PASSWORD`); Gateway admin `admin@switch.local` (password in the same `.env`).
> - llama.cpp: `llama serve -m ~/AI/models/Qwen3.5-9B-Q4_K_M.gguf --host 127.0.0.1 --port 8080 -c 8192` (log: `~/switch-hackathon/llama-serve.log`).
> - Ember: `python3 -m ember run` from `~/switch-hackathon/project` with env from `~/switch-hackathon/ember.env` (log: `~/switch-hackathon/ember.log`). It holds the **release-manager** role; its addressing policy was cleared via the Gateway (`PUT /agents/{id}/addressing-policy {"policy": null}`) so room members can @-mention it.
>
> **Tomorrow in ~10 minutes (recording path):**
> 1. If the PC rebooted: restart the stack (`docker compose ... up -d` in `~/switch-hackathon/stack`), then llama (command above), then Ember: `cd ~/switch-hackathon/project && set -a; . ~/switch-hackathon/ember.env; set +a; python3 -m ember run`.
> 2. **The one Console step:** install Switch Console (Step 1–2 below), connect it to the running server (Gateway http://localhost:3000 / API http://localhost:8000), sign in to Claude Code, and run ONLY the `agents:` part of `templates/nightshift.template.yaml` (or create `claude-reviewer` in Console) so the reviewer takes the free **reviewer** role — this is Beat 2 of DEMO.md, the only beat not exercised headlessly. Before that, replace the `<your-username>` placeholder in the template (Step 4/manual-setup §1) after pushing `demo-repo/` as `widgetapi`.
> 3. Open Mattermost (http://localhost:8065, user `user`), open `#nightshift`, follow DEMO.md. Tip for a clean take: Ember takes its role at startup, so for the on-camera hand-off, restart Ember just before Beat 3 — or post `!roles` first (Beat 1) with Ember already holding the role and narrate the day/night split from there. Repeat wraps are safe: Ember now *updates* the `v0.4 release notes` document instead of failing on the unique-name rule.
> 4. Push + submit (manual-setup §1 has the exact git commands).
>
> **Gotchas found live (already fixed in the code, listed so they don't bite again):**
> - A raw-protocol agent must be **added to the room** before `connect_to_room` works (Gateway: `POST /rooms/{room_id}/agents`). Ember's first run logged `Agent is not a member of this room` until then.
> - A registered agent's default addressing policy refuses @-mentions with a public "not permitted" notice; clear it with the Gateway call above (the template's reviewer uses `addressing: anyone` for the same reason).
> - Qwen chat templates reject a **second system message** (llama.cpp HTTP 500, "System message must be at the beginning") — Ember now folds room context into the single system message, bounds generation (`max_tokens`), and disables thinking for room answers.
> - Room-scoped document names are unique per room — repeat wraps update, not recreate.
>
> The from-scratch path below remains accurate for a clean machine.

This runbook takes you from a clean Ubuntu machine to Ember completing its first wrap in the `#nightshift` room. The steps follow the official Switch documentation — the quickstart, the template format, and the agent protocol as documented at docs.switchagents.ai and in the `sandbox-quantum/switch` repository.

**You need:**

- Ubuntu, with Docker installed (Switch Console runs your local Switch server with Docker)
- A Claude Code account (Console will prompt you to sign in)
- This repo, cloned
- Optional but recommended: a small GGUF model and `llama-server` (llama.cpp) for Ember's local brain. No model? Step 5 covers the scripted fallback — Ember works without one.

---

## Step 1 — Install Switch Console (~5 min)

1. Go to the releases page of the Switch repository: `github.com/sandbox-quantum/switch` → **Releases**.
2. Download the Linux build for your machine — the **.deb** (install it with `sudo apt install ./<file>.deb`) or the **AppImage** (make it executable and run it). Linux builds are in early access; both formats are published with each release.
3. Launch Switch Console.

## Step 2 — Let Console set up Switch, and sign in to Claude Code (~5 min)

1. Open Switch Console and follow its setup for running Switch **on this computer**. Console starts the stack with Docker, chooses free ports, creates the admin account, and signs you in — there is no configuration file to write.
2. This local Switch comes with **Mattermost** bundled, so your rooms have a chat app with no separate workspace to set up.
3. When Console prompts for an AI coding agent, sign in to **Claude Code**. In the pattern setup, this is the account the room's reviewer (`claude-reviewer`) runs under. (In our recorded demo the reviewer joined over the protocol instead — see README's live-status note — so this Console path is the template route, not the only one.)
4. Keep Console running. Agents that Console runs — including the reviewer — only answer while Console is open.

## Step 3 — Star-check with switch-buddy (~3 min)

Before building anything, prove the stack works end to end:

1. In Console, talk to **switch-buddy**, the built-in assistant that helps you set up agents and rooms.
2. Give it the quickstart task: ask switch-buddy to create a first agent and a room, then open the bundled Mattermost and address the agent in the channel.
3. You have a working stack when the agent replies to your addressed message in the room.

If this check fails, stop here and fix it first — everything after this step builds on the same path. The troubleshooting table at the end covers the common cases.

## Step 4 — Create the NightShift room from the template (~5 min)

1. In Switch Console, open **Templates** and import this repo's template file:

   ```
   templates/nightshift.template.yaml
   ```

2. Run the template. It creates:
   - the `#nightshift` room, with the room instructions from `room/`,
   - the two roles: **reviewer** (shared) and **release-manager** (exclusive),
   - the **claude-reviewer** agent (Claude Code, run by Console), holding the reviewer role,
   - a GitHub reference to the `widgetapi` demo repo, and a kickoff message that gets the room moving.
3. Open `#nightshift` in Mattermost and check the room is there with the reviewer as a member.
4. Type `!roles` in the room. You should see **reviewer** held by claude-reviewer and **release-manager** unheld. That empty chair is Ember's.

> Ember is not created by the template, by design: templates create Console-managed agents, and Ember is an external protocol agent that registers itself. Steps 5–6 are Ember checking in for its shift.

## Step 5 — Start Ember's brain (~2 min with a model, 0 without)

**Option A — local model (the real night shift).** Start llama.cpp's server with an explicit port:

```bash
llama-server --model <path-to-a-small-GGUF> --port 8080
```

Ember talks to it at `http://localhost:8080/v1` by default (OpenAI-compatible chat endpoint). A small instruction-tuned GGUF is plenty — Ember's jobs are reading context, summarising a git log, and drafting notes. Leave the server running.

**Option B — no model at all.** Set Ember's brain to scripted mode:

```bash
export EMBER_BRAIN=scripted
```

The scripted brain is deterministic: Ember registers, takes the role, reads context, and produces the wrap from the room and the git log using fixed composition logic. It is the right choice for a first run, a machine without a GPU, or isolating a problem — if the scripted run works, any remaining issue is in the model path, not the protocol path.

## Step 6 — Register Ember and launch it (~5 min)

Ember registers with the Switch server directly, using a registration token from the Gateway:

1. Open the **Gateway** for your local Switch server and go to the agents / registration area (**API Keys**). Create a registration token (API key of type `registration`). The person who creates the token becomes Ember's owner, and Ember inherits its access from its owner.
2. Note Ember's own API key when registration returns it — **the API key is returned once**. Ember's CLI stores it in its local state file (`.ember-state.json`, git-ignored) so later runs don't need it again.
3. Launch Ember from this repo's root:

```bash
export SWITCH_BASE_URL=<your Switch server address>
export EMBER_REGISTRATION_TOKEN=<the registration token from the Gateway>
# Option A only — point Ember at your local model (this is the default):
export EMBER_LLM_BASE_URL=http://localhost:8080/v1
# Option B only — skip the model:
# export EMBER_BRAIN=scripted

python3 -m ember run
```

Ember registers as `ember`, opens its event connection, and starts its 2-second heartbeat. Leave the process running — Ember answers only while it holds its connection to Switch.

## Step 7 — First-contact checklist (~3 min)

Work through these in order, in the `#nightshift` room in Mattermost:

- [ ] **Ember is in the room.** Ember appears in the `#nightshift` member list.
- [ ] **Ember holds its role.** Ask Ember to take the job — send: `@ember take the release-manager job and wrap the day` — then type `!roles`. **release-manager** is held by `ember`, and because the role is exclusive, nobody else can hold it at the same time.
- [ ] **Smoke test the wrap.** With Ember holding the role, send:

  ```
  @ember wrap
  ```

  Ember reads the room context, reads the `demo-repo/` git log, creates the room document **"v0.4 release notes"**, and posts the wrap in chat: what merged, what's blocked, what's next.
- [ ] **Ask the morning question.** Send: `@ember what's still blocking v0.4?` Ember answers from the room document and context, in the room.

That's a full night shift. For the complete choreographed version — reviewer first, then the hand-off — follow [DEMO.md](DEMO.md).

---

## Troubleshooting

| Symptom | What's happening | Fix |
|---|---|---|
| Agents stop answering entirely | Switch Console is closed. Console-run agents only answer while Console is running, and a server on your own computer answers only while the computer is on. | Reopen Console and wait for the agents to reconnect, then address the agent again. |
| Ember is silent in the room | Ember only acts on messages that address it, and only in rooms where it is a member and permitted to answer. A new agent answers only its owner until the owner permits more people, per room. | Check Ember is a member of `#nightshift`; check Ember is permitted to answer you in this room (agent settings, per room); address it by its exact name — `@ember` — at the start of your message. Names are case-insensitive, but `@ember-2` or a typo addresses nobody. |
| Ember is silent everywhere | Ember's process isn't running, or its connection dropped. Ember answers only while it holds its connection to Switch. | Check the `python3 -m ember run` process and its log; relaunch it if it exited. |
| Ember replies, but the wrap looks mechanical | The scripted brain is active, or the local model endpoint is down and Ember fell back. Ember's log carries a fallback line when the LLM call fails and the scripted brain takes over. | Check Ember's log for the scripted-fallback line; check `llama-server` is running on port 8080; check `EMBER_LLM_BASE_URL` points at `http://localhost:8080/v1`; unset `EMBER_BRAIN=scripted` if you set it. |
| `llama-server` port confusion | llama.cpp's default port is easy to mismatch with the client's expectation. | Always pass an explicit `--port 8080` to `llama-server`, and match `EMBER_LLM_BASE_URL` to it. |
| Registration is rejected | A registration token authenticates registration only, and an agent API key can't register an agent — the two keys are not interchangeable. | Create a fresh key of type `registration` in the Gateway and use it as `EMBER_REGISTRATION_TOKEN`. Ember's own API key (returned once at registration) is for its connection and ops calls. |
| The reviewer doesn't answer | The Console-run Claude agent answers only while Console is running and its Claude Code sign-in is live. | Check Console is open and signed in to Claude Code; address the reviewer by its exact name, `@claude-reviewer`. |
| Template run stops before creating the room | A template run stops if an agent or reference it names is missing on this server and the template doesn't create it. | Re-run the star-check (Step 3) so the base setup exists, then run the template again. |
