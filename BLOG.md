# We gave our release process a night shift — and it costs $0

Every team we know has the same end-of-day ritual. Someone scrolls back through the day's pull requests, chat threads, and half-finished conversations, and writes the wrap-up: what merged, what's stuck, what ships tomorrow. Release notes. A status summary. The list of blockers nobody wants to discover at 10 a.m.

It's necessary work. It's also mechanical work. So we asked: can't an agent do this?

The honest answer was "yes, but look at the bill." A cloud agent on wrap-up duty reads your whole day, every day — every message, every diff, every thread — and you pay per token for all of it, forever. Worse, your code and your team's discussion travel to a third-party cloud to get summarised. For the *hard* parts of engineering — reviewing a tricky auth change, say — a frontier model earns that cost. For collecting a git log and drafting release notes? This half of the job doesn't need a frontier model. It needs a teammate who is in the room, knows the context, and never forgets to do the wrap.

So we built the night shift instead of buying it.

## The discovery: Switch ships no agents

We built NightShift on [Switch](https://docs.switchagents.ai), and what made it possible is a sentence from its own documentation: Switch ships no agents and no models. A Switch room is a shared workspace — people and agents in a chat channel, with roles, documents, references, and permissions — and any agent can join it, from any vendor, as long as it speaks the agent protocol.

The usual way to use that freedom is through Switch Console, which runs a well-known coding agent for you — Claude Code, Codex, OpenCode — and that agent joins the room. That's the day shift, and we kept it: our `#nightshift` room has a Claude Code agent, claude-reviewer, holding the reviewer role — in the recorded demo it joins over the protocol directly (our Console's secure storage refused to cooperate on demo day, and the protocol didn't care), and on this machine its model routes locally through our own router.

But "if it speaks the protocol, it can join" invites a ruder question: what if the agent isn't a product at all? What if it's a program we write ourselves, backed by a model running on our own GPU?

## Writing an agent with nothing but the standard library

Switch's agent protocol is documented, and it's refreshingly plain. An agent registers with the server — one call, authenticated by a registration token you create in the Gateway, which returns the agent's API key exactly once. Then it opens an event connection, listens for room events over a server-sent events stream, sends a heartbeat every two seconds, and does everything else through operations: HTTP calls named `read_context`, `post_message`, and `create_room_document`. Roles are operations too — an agent defines them, takes them, releases them.

There is no SDK to install, so we didn't install one. Our agent, Ember, is Python using only the standard library: registration, the event loop, the heartbeat, the ops client, all of it. Its "brain" is a small open model served locally by llama.cpp — Ember sends it the room context as an ordinary chat request to `localhost`, and the model helps compose the wrap. Ember also has a second brain: a deterministic scripted mode that produces the wrap from the room context and the git log with fixed logic. Flip one environment variable and Ember runs with no model at all — which made it testable anywhere, and our test suite runs fully offline against a mock server that implements the documented protocol.

The moment that made the project real wasn't Ember's first message. It was the role. In our room, release-manager is an *exclusive* role: only one member can hold it at a time. We typed `@ember take the release-manager job and wrap the day`, and Ember took it — the same role mechanism the cloud agent's reviewer job uses, exercised by a program we'd written that morning, running a model on the machine under the desk. Then it read the room's context and our demo repo's git log, created a room document called "v0.4 release notes," and posted the wrap: what merged, what's blocked, what's next. Next morning, "what's still blocking v0.4?" gets an answer from that document — in the room, under the room's permissions.

Nothing about that flow works without Switch. Take the room away and Ember is a script that reads a git log. The roles, the shared context, the document, the permissions — those are the product, and they're Switch's.

## What it costs, and what we'd do next

The night shift's invoice is easy to read: zero cloud tokens. In the setup we recorded, the day shift spent none either — the reviewer's model routed locally on this machine. That's not the required shape: the split we wanted is cloud where it earns, local where it doesn't, and the reviewer seat takes a frontier model unchanged whenever you point it at one. Privacy comes free for Ember's work: code never leaves the machine.

The night before submitting, we torture-tested the live system instead of rehearsing it: we killed the model mid-shift and Ember fell back to its scripted brain and kept answering until the model came back; we tried to talk it into deleting its own release notes and marking everything shipped, and it refused both; we flooded the room with 55 messages and, after one real fix to how much context it reads, it still found the facts planted at the very start. It also failed honestly: a blocker written in Hinglish slipped straight past it. That miss is the true shape of a small local model — strong on the mechanical work it was hired for, with edges you can find if you push — and we'd rather publish the miss than hide it.

If you're trying Switch for the first time, take the path we took: do the quickstart with switch-buddy, make one room from a template, then ask what a small agent of your own could own. Start with a narrow, forgiving job — a wrap, a summary, a checklist — and give it a role, not just a prompt.

Next for NightShift: a second room. A link from `#nightshift` to a morning-brief room, with Ember a member of both, carrying the wrap across so the day starts where the night ended.

**Code:** https://github.com/PravWeb/nightshift-ember · **Demo:** [demo video — FINAL LINK TO BE FILLED AFTER SUBMISSION/UPLOAD] · Built for Flip the Switch (Track 1 — Best Business Workflow).
