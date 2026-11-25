---
name: wrap-up
description: End-of-session close-out. Proves every file the session wrote actually landed on disk (the file list comes from the session transcript, not memory), checks what the session changed for duplicate facts, stale pointers, CLAUDE.md bloat and dropped open items, then writes a paste-ready handoff summary for a fresh chat and offers to update the project's state file. Use whenever the user says "wrap up", "wrap it up", "let's wrap", "/wrap-up", "close out the session", "end of session", "handoff summary", "summary for a new chat", "what did we change this session", "verify everything landed", "before I start a new chat", or otherwise signals the session is ending and wants a clean handoff, even if they never say "wrap-up".
---

# Wrap-up

Three steps, in order: verify, check, hand off.

## Your own changes (read first, every time)

Before anything else, read `~/.solnest/wrap-up/my-instructions.md` if it exists and
follow it. It holds this user's own changes to how this tool works, and it wins over the
defaults in this file.

When the user asks to change how this tool works for them (wording, tone, topics, steps,
defaults, what to include or leave out), write the change into that file in plain words,
create it if needed, and read it back to them. **Never edit this tool's own files for
that.** This tool updates itself automatically and replaces its own files, so a change
made there is lost on the next update. The one file here that is theirs is
`references/homes.md` (where things live on their machine): an update never touches it,
and neither does anything else they added to this folder.

The reason this exists: a session's memory of its own work is the least reliable record there is. Tool calls report success on writes that another session clobbers a minute later, that a sync job reverts, or that were only ever planned and never made. Context compaction erases the first half of a long session. So the file list comes from the transcript, and "done" means you looked at the file on disk this turn.

Before starting, read `references/homes.md`. It says where facts, pointers and the state file live on this machine, and which "missing" files are expected to vanish. Those details change per machine, so they live there and not here.

Two ground rules for the whole routine:

- **Verify against evidence that already exists.** Files, logs, git history, read-only lookups. Don't open new investigations, reproduce bugs, or run live tests during a wrap-up. That's new work with its own blast radius, and it turns a five-minute close-out into a second session. If a claim the session made can't be checked from existing evidence, mark it "unverified" and put the test under Open.
- **Match by name or content, never by coincidence.** A log that says "1 file dropped" around the right time does not prove it was your file. Say "probably" until the name or the content turns up.

**Snapshot before you fix.** Before the first edit this routine makes, copy each file you're about to change into the session scratchpad (or `/tmp/wrap-up-<date>/` if there's none), keeping relative paths. Say where the copies are, so every fix is a one-step undo.

## Step 1: Verify writes

1. **Get the list from the transcript.** Run:

   ```bash
   ~/.claude/skills/wrap-up/bin/py ~/.claude/skills/wrap-up/scripts/session_writes.py
   ```

   (`bin/py` is the Python that setup found. If it is missing, use `python3`, or on Windows `py`. Claude Code's Git Bash shell understands `~`.)

   It reads `CLAUDE_CODE_SESSION_ID`, finds the transcript (and any subagent transcripts), and for every Write/Edit/MultiEdit/NotebookEdit checks that the file exists, how its mtime compares with the session's last write, and that the content each successful edit wrote is still in the file. A later edit in the same session that legitimately replaced it counts as fine. It also lists two things it cannot verify alone: Bash commands that look like they wrote, moved or deleted something, and MCP/Artifact calls that changed state outside the filesystem.

   If the env var is missing, pass `--transcript <path>`: the newest `.jsonl` in `~/.claude/projects/<cwd with / replaced by ->/` that contains something distinctive from this session. If no transcript can be found at all, build the list from the conversation and say plainly that you did, because that list is weaker.

2. **Add what the scanner can't see.** Files written by scripts the session ran (a Python job that writes a report), writes inside subagents that didn't leave a transcript, and anything you remember doing that isn't on the list. Check these by hand.

3. **Resolve every row that isn't OK.** For each one:
   - `MISSING-FILE`, `MISSING-CONTENT`, `DIVERGED`: read the file and work out what happened: a later edit, another session, a sync job, a write that never landed. Check `references/homes.md` for files that are designed to disappear before calling it lost. If the change is still wanted, redo it and rerun the scanner to confirm. If another session owns the file now, don't overwrite it; merge or flag it.
     Re-apply without asking only when the user asked for exactly that change this session and nothing suggests the revert was deliberate. If the change touches prices, money or outbound messages and its intent is ambiguous (for example "from October" when the file holds a single value), or if the revert might have been on purpose, don't re-apply. Put it to the user as a question with your recommendation.
   - `FAILED` / `UNCONFIRMED`: the tool call errored or never returned. If the scanner shows a later successful write to the same file, it was retried. Otherwise it's a gap: fix it now or carry it into Open.
   - `WARN` (mtime): something touched the file after this session did, or it was restored to an older copy. Confirm the content is still what the session intended.
   - Bash candidates: for each command that really wrote something, confirm the target exists with the expected content (`ls -l`, then grep a distinctive phrase). Moves and deletes feed Step 2's broken-reference check.
   - External writes: read back through the same MCP (get the doc, row, post or event you changed) where a read tool exists. If none exists, label it "not re-verified" in the summary.

4. Anything you fixed, say so plainly ("X had not landed, the Edit was reverted by …, re-applied and confirmed"). Nothing goes into the summary as done unless it passed this step.

## Step 2: Gaps and redundancies

Scope is strictly what Step 1 found this session changed. This is not a full audit.

1. **One home per fact.** For each durable fact, rule, cost figure or convention the session wrote (prose, not code), grep its most distinctive words across the fact homes listed in `references/homes.md`. If the session created a second home, resolve it. Don't just flag it. Pick the canonical home: usually the older one, or wherever the project keeps that kind of fact (costs in the cost table, rules in rules). Move anything genuinely new into it, and replace the session's copy with a one-line pointer to the canonical file. Never delete, since a pointer is reversible and a delete isn't. If both copies predate this session, flag it and leave it; that's outside this session's scope.

2. **Broken references.** For every path the session renamed, moved or deleted (the scanner's MOVE/DELETE lines, plus any file the session replaced with a new one elsewhere), grep the old path and the old basename across the pointer files in `references/homes.md`. A hit that still points at the old location is a broken reference. Fix it if it's yours to fix, flag it if not.

3. **CLAUDE.md length guard.** Only if a CLAUDE.md was touched this session. If it has a workflows, skills or routing index, each entry must stay at name + one line + path, with the detail living in the linked file. Trim anything that grew past that. If the project has a written length-guard rule, read that rule and apply its actual wording. Don't work from memory of it. If there's no index section, compare the file's size before and after the session and flag any block that reads like documentation rather than an instruction.

4. **New conventions.** If the session introduced a new folder convention or workflow, find how an existing sibling is wired in (folder map, skill routing table, index, template) and wire the new one into the same places, in the same format, keeping the length guard. When a sibling shows the pattern, just do it and report it. Leaving it unwired is how conventions become one-offs that future projects never inherit. Ask only when there's no sibling to copy, or when the wording needs a decision only the user can make (for example what the trigger phrases should be).

5. **Open items.** Scan the whole conversation for anything flagged open, a watch-item, "not done yet", "later", "TODO", "blocked on", "needs <person>", deferred, parked or skipped, plus anything that failed Step 1 and wasn't fixed. Every one goes into the summary's Open section. Dropping these quietly is the most common way a handoff fails.

Report Step 2 as a short list: finding, then what you did about it. If a check found nothing, one line saying so is enough.

## Step 3: Handoff summary

Output the summary in one fenced `markdown` block so it copies in one click. Use this template:

```markdown
# Handoff: <topic> (<YYYY-MM-DD>)

## Changed this session
- `<path>`: created|edited. <one line: what, and why it matters>
- External: <MCP/Artifact write>, verified | not re-verified

## Decisions and why
- <decision>: <the reasoning a fresh chat needs so it doesn't reopen it, including the alternative that was rejected and why>

## Open / deferred / flagged
- <item>: <current state, what blocks it, who owns the next move>

## Where the detail lives
- <topic>: `<path>`

## Next chat should start by
<one or two sentences>
```

Rules for the block:
- One line per file. Many files in one folder: group them under the folder.
- Only items that passed Step 1 go under "Changed". Failed or unverified items go under Open, labelled as such.
- A decision without its reason is just an outcome. "Moved the cache out of the vault" is an outcome. "Moved the cache out of the vault because Sync bills per revision and it was 80% of daily sync weight" is a decision a fresh chat can respect.
- Point to files, don't restate them. The summary is a map, not a copy.
- No secrets, tokens or keys, even partial ones.
- Keep it pasteable: aim for under ~60 lines.

**Then the state-file offer.** If the session changed an ongoing status, priority or decision, name each change and offer to write it to the project's state file now. `references/homes.md` says where that is. If the project has a `current-state.md`, show the exact lines you'd change and ask "apply this?". A plain yes applies it. No typed codes or confirmation rituals. If the project has no `current-state.md`, don't create one. Use the equivalent route in `references/homes.md` and say which route you're offering. Never say the state file was updated unless you wrote it and read it back.

## Output order

1. Step 1 result: counts, anything fixed, anything still failing, and where the pre-fix snapshots are.
2. Step 2 findings.
3. The handoff block.
4. The state-file offer and any other questions, numbered, so a reply can be "yes to 1 and 3".
5. Optional, one line each: anything urgent you happened to notice outside this session's work. Don't chase it.

Keep the prose around the block short. The block is the deliverable.
