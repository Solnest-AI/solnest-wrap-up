# Where things live on this machine

This file tells the wrap-up routine where your facts, pointers and state file live. It ships with sensible defaults that fit most Claude Code setups. Setup (or any later session) may fill in the "Your setup" section below. If a path here stops resolving, trust the disk, not this file, and fix this file.

## State file (Step 3 offer)

- Look for a `current-state.md` in the project you are wrapping up: `find . -maxdepth 3 -iname current-state.md` (or the project's own status file, if its `CLAUDE.md` names one). If one exists, that is the state file. If none exists, do not create one.
- If there is no state file, the route for status changes is the project's `CLAUDE.md` (only for durable rules, never for day-to-day status) or a note in the user's own notes system, if "Your setup" below names one. Otherwise, put the status changes in the handoff block only and say so.
- Never hand-edit a file that a scheduled job rewrites (for example an auto-generated summary). If "Your setup" lists such files, respect that.

## Fact homes (Step 2.1, one home per fact)

Grep these for a fact before calling it new:
- `~/.claude/CLAUDE.md` (the user's global instructions)
- `~/.claude/rules/*.md`, if that folder exists
- Auto-memory, if present: `~/.claude/projects/<escaped-cwd>/memory/*.md`, indexed by `MEMORY.md` in the same folder
- The project's own `CLAUDE.md`, plus any `docs/` or `README.md` the project uses for conventions
- Anything listed under "Your setup" below

## Pointer files (Step 2.2, broken references)

After a rename, move or delete, grep the old path and old basename in:
- Everything in "Fact homes" above
- `~/.claude/skills/*/SKILL.md` (skills often reference script paths; a symlinked skill breaks silently when its target moves)
- `~/.claude/settings.json` and the project's `.claude/settings.json` (hook commands reference script paths)
- Scheduled jobs that run scripts: on macOS `crontab -l` and `~/Library/LaunchAgents/*.plist`; on Windows `schtasks /Query /FO LIST /V`
- Anything listed under "Your setup" below

## Files that are supposed to disappear

- Files in the session scratchpad or system temp folders are ephemeral. Don't list them under "Changed" unless they were the deliverable.
- Anything listed under "Your setup" below as auto-drained or auto-rotated.

## Search gotchas

- On macOS, `~/Downloads`, `~/Desktop` and `~/Documents` can be blocked by privacy permissions for some processes. A denied listing can look like an empty folder. Don't report "nothing there" from a listing that might have been denied; use Spotlight (`mdfind`) or ask the user.
- `grep -r` and `find` on a symlinked folder need a trailing slash (`folder/`) or they may return nothing, which looks the same as "not found".

## Machine behaviour worth knowing

- The user may run several Claude sessions at once. A DIVERGED or "modified after this session's last write" file is often another live session editing the same file. Read and merge, don't overwrite.
- When a change needs the user's go-ahead, ask a plain question. A plain yes applies it.

## Your setup

Fill this in for your machine. Leave a line out if it does not apply.

- Notes system or knowledge base (for example an Obsidian vault) and where status notes go: (none recorded)
- Files that a scheduled job rewrites, so never hand-edit: (none recorded)
- Extra fact homes to grep: (none recorded)
- Files designed to disappear (inbox folders that get drained, rotated logs): (none recorded)
