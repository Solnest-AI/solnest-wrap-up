If the user said "set this up", follow SETUP below.

# Wrap-up (Solnest AI)

This repo installs the `wrap-up` skill: an end-of-session close-out. It reads the session log to list every file the session wrote, checks each one landed, looks for duplicate facts and broken references the session created, and writes a paste-ready handoff summary. The scanner (`scripts/session_writes.py`) is standard-library Python 3.9+ and read-only.

What is in here:
- `skill/wrap-up/`: the skill (`SKILL.md`, `scripts/`, `references/homes.md`). It installs to `~/.claude/skills/wrap-up`.
- `install.sh`: the installer. `VERSION` and `CHANGELOG.md`: what release this is.

## Your own changes (read first, every time)

Before anything else, read `~/.solnest/wrap-up/my-instructions.md` if it exists and
follow it. It holds this user's own changes to how this tool works, and it wins over the
defaults in this file.

When the user asks to change how this tool works for them (wording, tone, topics, steps,
defaults, what to include or leave out), write the change into that file in plain words,
create it if needed, and read it back to them. **Never edit this tool's own files for
that.** This tool updates itself automatically and replaces its own files, so a change
made there is lost on the next update. The one file in the skill folder that is theirs is
`references/homes.md` (where things live on their machine): an update never touches it,
and neither does anything else they added to that folder.

## Rules for you (Claude) during setup

- You run every command yourself with your Bash tool. The user never opens a terminal. On Windows, Claude Code runs Bash commands in Git Bash, where these commands (including `~`) work.
- One step per message. Do not report success until you have seen real output.
- This tool needs no accounts and no keys. Never ask for one.

## SETUP

### Step 1: Install

Tell the user in one line: "Installing the wrap-up skill. About a minute, nothing for you to do." Then run one of these:

- You are reading this from the GitHub page (no local copy of this repo):

  ```bash
  bash -o pipefail -c "curl -fsSL https://raw.githubusercontent.com/Solnest-AI/solnest-wrap-up/main/install.sh | bash"
  ```

- You already have this repo as a folder on this computer: `bash "<this folder>/install.sh"`

The installer copies the skill to `~/.claude/skills/wrap-up`, finds Python 3.9 or newer (or installs one for this user, no admin rights needed), writes a small launcher (`bin/py`) so the skill always uses that Python, and starts the scanner once to prove it works. Running it again is safe: it keeps the user's `references/homes.md`.

### Step 2: Read the checklist it printed

- Every line starts with `[ok]`: go on to Step 3.
- `STOP: ... holds a different skill` or `... a link or a git checkout`: something else already lives at `~/.claude/skills/wrap-up`. Nothing was changed. Tell the user what you found and ask what they want to do with it. Do not delete it yourself.
- `ERROR: could not download`: usually the network. Run Step 1 once more.
- `ERROR: no working Python`: send the user to https://www.python.org/downloads/ (on Windows they must tick "Add python.exe to PATH"). When they say it is installed, run Step 1 again.
- `[!!] scanner`: run Step 1 once more. If it repeats, send the full output to hello@solnestai.com.

### Step 3: Personalize `references/homes.md` (optional, 1 minute)

Check quietly for things that belong in the "Your setup" section of `~/.claude/skills/wrap-up/references/homes.md`:
- `~/.claude/hooks/wiki/config.json` exists: the user has the Solnest Second Brain kit. Read only its `vault` value and record: notes system = that vault; `_wiki/hot.md` is rewritten nightly (never hand-edit); fact homes include `<vault>/_wiki/`; status changes go to a decision page in `<vault>/_wiki/decisions/`.
- `~/.claude/rules/` exists: already covered by the defaults.

Then ask the user one question: "Do you keep project status anywhere I should know about, like a notes app, a current-state file, or a project board? If not, just say no." Record the answer in "Your setup". If the answer is no, leave the defaults.

If "Your setup" already has answers in it (a repair or a second install), leave them and skip the question.

### Step 4: Real test (read-only)

Run the scanner on this setup session itself:

```bash
~/.claude/skills/wrap-up/bin/py ~/.claude/skills/wrap-up/scripts/session_writes.py
```

It uses the `CLAUDE_CODE_SESSION_ID` value that Claude Code sets. Expect a report that starts with `# Session writes:` and lists the files this setup session wrote (for example `homes.md` if you edited it), each marked OK.

If it says the session id is missing, find the newest session log instead:

```bash
ls -t ~/.claude/projects/*/*.jsonl | head -1
```

then run the scanner again with `--transcript "<that path>"` added at the end.

Show the user the first lines of the report.

### Step 5: Turn on automatic updates (required, silent)

Run this exactly:

```bash
SKILL="$HOME/.claude/skills/wrap-up"; "$SKILL/bin/py" "$SKILL/scripts/solnest_autoupdate.py" register --name wrap-up --folder "$SKILL" --update '{python} scripts/update.py' --after '{python} scripts/session_writes.py --help' --undo '{python} scripts/update.py --undo'
```

From now on the skill keeps itself on the latest release with no one asking: once a day, in the background when Claude Code starts, it installs the newest published release and checks that the scanner still starts. It never touches `references/homes.md` or any file the user added, and if a new release fails that check it puts the old version back by itself. Relay the one line it prints. Nothing else to tell them.

### Step 6: Tell the user what worked

Short checklist: skill installed (path), homes.md personalized or left on defaults, scanner ran and found N files, automatic updates on. Then: "Next time you finish a working session, just say: wrap up. You'll get a handoff block you can paste into a fresh chat."

The skill loads by itself the next time they open Claude Code. In this chat, if they say "wrap up" right away, read `~/.claude/skills/wrap-up/SKILL.md` and follow it from the top.

## Update

Updates install themselves (Step 5). `references/homes.md` and any file the user added are never touched. Changes the user asked for live in `~/.solnest/wrap-up/my-instructions.md`, outside the skill folder, so they survive every update.

Only when the user asks to update now:

```bash
SKILL="$HOME/.claude/skills/wrap-up"; "$SKILL/bin/py" "$SKILL/scripts/update.py" && "$SKILL/bin/py" "$SKILL/scripts/session_writes.py" --help >/dev/null && echo "[ok] scanner starts"
```

Then run the Step 5 line once more, so a newer auto-updater is picked up. To go back one version: `"$HOME/.claude/skills/wrap-up/bin/py" "$HOME/.claude/skills/wrap-up/scripts/update.py" --undo`. If `scripts/update.py` is missing (a copy from before automatic updates), run Step 1 instead, then Step 5.

"Is it updating itself?": `~/.claude/skills/wrap-up/bin/py ~/.solnest/autoupdate.py status`. Use `pause` in place of `status` to stop all automatic updates, and `resume` to turn them back on.

If `status` shows the last check failed, offer to update now with the line above.

## Repair

Run Step 1 again, then Step 5. It keeps `references/homes.md`.

## Uninstall

```bash
~/.claude/skills/wrap-up/bin/py ~/.solnest/autoupdate.py remove --name wrap-up
```

Then, after a plain yes from the user, delete the folder `~/.claude/skills/wrap-up`.
