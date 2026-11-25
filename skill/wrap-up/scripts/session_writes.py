#!/usr/bin/env python3
"""List every file this Claude Code session wrote, and check that each one landed.

The list comes from the session transcript, not from the model's memory, so it
survives context compaction and catches writes the model has forgotten about.

Transcript: ~/.claude/projects/*/<session_id>.jsonl, plus any subagent
transcripts under ~/.claude/projects/*/<session_id>/.

For every Write / Edit / MultiEdit / NotebookEdit it checks:
  - the file still exists
  - its mtime vs. the session's last write to it (reverted? touched by something else?)
  - the content each successful edit wrote is still in the file (or was
    superseded by a later edit in this same session)
It also lists, for manual review, the Bash commands that look like they wrote,
moved or deleted something, and the MCP / Artifact calls that changed state
outside the filesystem. Those can't be verified from the transcript alone.

Usage:
  python3 session_writes.py                    # current session (CLAUDE_CODE_SESSION_ID)
  python3 session_writes.py --session <id>
  python3 session_writes.py --transcript <path.jsonl>
  python3 session_writes.py --json             # machine-readable

Exit code: 0 when the scan ran (whatever it found), 1 only when the transcript
could not be found or read. Findings are in the report, not the exit code.

Python 3.9 compatible. Standard library only. Works on macOS, Linux and Windows.
"""

import argparse
import datetime as dt
import glob
import json
import os
import re
import sys

FILE_TOOLS = ("Write", "Edit", "MultiEdit", "NotebookEdit")

# Bash commands that probably changed the filesystem. False positives are fine:
# the model reviews this list, it is not a verdict.
# Redirects are matched against the command with quoted strings blanked out, so a
# '>' inside a sed/grep expression or an echo'd string doesn't count.
BASH_REDIRECT_RE = re.compile(r"(?:^|[^0-9&>])>>?\s*(?!&|/dev/null)[^\s|;&)]")  # > f, >> f (not 2>&1, >/dev/null)
QUOTED_RE = re.compile(r"'[^']*'|\"(?:\\.|[^\"\\])*\"")
BASH_WRITE_RE = re.compile(
    r"\btee\b"
    r"|\bsed\s+(?:-[a-zA-Z]*\s+)*-i"
    r"|\bperl\s+-[a-zA-Z]*i"
    r"|(?:^|[\s;&|(])(?:cp|mv|rm|rmdir|mkdir|touch|ln|install|rsync|unzip|chmod|chown)\s"
    r"|\bgit\s+(?:commit|push|mv|rm|tag|checkout|reset|stash|merge|rebase|restore|apply)\b"
    r"|\btar\s+-?[a-zA-Z]*x"
    r"|\b(?:launchctl)\s+(?:load|unload|bootstrap|bootout|kickstart|enable|disable)\b"
    r"|-delete\b"
    r"|open\([^)]*['\"][wax]\+?b?['\"]"
    r"|\.write_text\(|\.write_bytes\(|json\.dump\(|shutil\.|os\.(?:remove|rename|replace|unlink|makedirs)\("
    r"|\bplutil\s+-(?:replace|insert|remove|convert)"
    r"|\bdefaults\s+write\b"
)
BASH_MOVE_DELETE_RE = re.compile(
    r"(?:^|[\s;&|(])(?:mv|rm|rmdir|unlink)\s"
    r"|\bgit\s+(?:mv|rm)\b"
    r"|-delete\b"
    r"|shutil\.(?:move|rmtree)|os\.(?:remove|rename|replace|unlink)\("
)

# MCP tool name suffixes that change state. Anything matching a read verb is skipped.
MCP_WRITE_RE = re.compile(
    r"(?:^|[_-])(create|update|delete|send|set|apply|upsert|add|remove|publish|post|move|"
    r"rename|trash|write|modify|manage|batch|append|insert|import|upload|deploy|merge|edit|"
    r"save|respond|mark|tag|assign|cancel|copy|share|activate|pause|resume|submit|draft|"
    r"reply|forward|label|schedule|lock|unlock|restore|record|void|patch|train|attach|bulk|"
    r"enable|disable|purchase|connect|disconnect|accept|refresh|execute|run|clone|duplicate|"
    r"approve|archive|recover|pin|unpin|toggle|boost|finalize|reset|rebase)(?:$|[_-])",
    re.I,
)
MCP_READ_RE = re.compile(
    r"(?:^|[_-])(get|list|search|read|query|fetch|lookup|find|describe|inspect|check|status|"
    r"health|whoami|preview|count|explain|trace|context|diagnose|estimate)(?:$|[_-])",
    re.I,
)

MTIME_SLACK_S = 5  # clock + write latency slack when comparing mtime to a write


def parse_ts(s):
    if not s:
        return None
    try:
        return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def fmt_ts(t):
    if t is None:
        return "?"
    return dt.datetime.fromtimestamp(t).strftime("%Y-%m-%d %H:%M:%S")


def find_transcripts(session_id, transcript):
    if transcript:
        main = os.path.expanduser(transcript)
        if not os.path.isfile(main):
            return None, []
        sid = os.path.splitext(os.path.basename(main))[0]
        base = os.path.dirname(main)
    else:
        hits = glob.glob(os.path.expanduser("~/.claude/projects/*/%s.jsonl" % session_id))
        if not hits:
            return None, []
        hits.sort(key=os.path.getmtime, reverse=True)
        main = hits[0]
        sid = session_id
        base = os.path.dirname(main)
    subs = sorted(glob.glob(os.path.join(base, sid, "**", "*.jsonl"), recursive=True))
    return main, subs


def iter_blocks(path, source):
    """Yield (kind, timestamp, block, record) for tool_use / tool_result blocks."""
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            ts = parse_ts(rec.get("timestamp"))
            msg = rec.get("message")
            if not isinstance(msg, dict):
                if ts is not None:
                    yield ("tick", ts, None, rec)
                continue
            content = msg.get("content")
            if isinstance(content, list):
                for b in content:
                    if not isinstance(b, dict):
                        continue
                    if b.get("type") == "tool_use":
                        yield ("use", ts, b, rec)
                    elif b.get("type") == "tool_result":
                        yield ("result", ts, b, rec)
            if ts is not None:
                yield ("tick", ts, None, rec)


def result_text(block):
    c = block.get("content")
    if isinstance(c, list):
        parts = []
        for x in c:
            if isinstance(x, dict) and x.get("type") == "text":
                parts.append(x.get("text", ""))
        c = " ".join(parts)
    return str(c or "")


def one_line(s, n=180):
    s = " ".join(str(s).split())
    return s if len(s) <= n else s[: n - 1] + "…"


def expected_fragments(name, inp):
    """Return list of (fragment, kind) the op should have left in the file."""
    if name == "Write":
        return [(inp.get("content", ""), "full")]
    if name == "Edit":
        return [(inp.get("new_string", ""), "edit", inp.get("old_string", ""))]
    if name == "MultiEdit":
        return [(e.get("new_string", ""), "edit", e.get("old_string", "")) for e in inp.get("edits", []) or []]
    if name == "NotebookEdit":
        if inp.get("edit_mode") == "delete":
            return []
        return [(inp.get("new_source", ""), "notebook")]
    return []


def read_file_text(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except (OSError, IOError) as e:
        return None, str(e)
    if path.endswith(".ipynb"):
        try:
            nb = json.loads(text)
            cells = nb.get("cells", [])
            srcs = []
            for c in cells:
                s = c.get("source", "")
                srcs.append("".join(s) if isinstance(s, list) else str(s))
            text = "\n".join(srcs)
        except ValueError:
            pass
    return text, None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--session", default=os.environ.get("CLAUDE_CODE_SESSION_ID"))
    ap.add_argument("--transcript")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-subagents", action="store_true")
    args = ap.parse_args()

    if args.transcript:
        args.session = os.path.splitext(os.path.basename(args.transcript))[0]
    if not args.session and not args.transcript:
        print("ERROR: no session id. CLAUDE_CODE_SESSION_ID is unset; pass --session or --transcript.", file=sys.stderr)
        return 1
    main_t, subs = find_transcripts(args.session, args.transcript)
    if not main_t:
        print("ERROR: transcript not found for session %s (looked in ~/.claude/projects/*/)." % (args.session or args.transcript), file=sys.stderr)
        return 1
    if args.no_subagents:
        subs = []

    uses = {}       # tool_use_id -> dict
    results = {}    # tool_use_id -> (is_error, text, toolUseResult)
    order = []
    t_first, t_last = None, None

    for path, source in [(main_t, "main")] + [(s, "subagent:" + os.path.basename(s)) for s in subs]:
        try:
            for kind, ts, b, rec in iter_blocks(path, source):
                if ts is not None:
                    t_first = ts if t_first is None else min(t_first, ts)
                    t_last = ts if t_last is None else max(t_last, ts)
                if kind == "use":
                    uid = b.get("id")
                    uses[uid] = {"id": uid, "name": b.get("name", ""), "input": b.get("input") or {}, "ts": ts, "source": source}
                    order.append(uid)
                elif kind == "result":
                    results[b.get("tool_use_id")] = (bool(b.get("is_error")), result_text(b), rec.get("toolUseResult"))
        except (OSError, IOError) as e:
            print("ERROR: could not read %s: %s" % (path, e), file=sys.stderr)
            if path == main_t:
                return 1

    files = {}          # realpath -> record
    failed_ops = []
    bash_writes = []
    external = []

    for uid in order:
        u = uses[uid]
        name, inp = u["name"], u["input"]
        res = results.get(uid)
        is_err = res[0] if res else None
        if name in FILE_TOOLS:
            p = inp.get("file_path") or inp.get("notebook_path") or ""
            if not p:
                continue
            rp = os.path.realpath(os.path.expanduser(p))
            rec = files.setdefault(rp, {"path": p, "realpath": rp, "ops": [], "created": False})
            tur = res[2] if res else None
            op = {"tool": name, "ts": u["ts"], "ok": is_err is False, "pending": res is None,
                  "frags": expected_fragments(name, inp), "source": u["source"]}
            if not rec["ops"] and name == "Write" and isinstance(tur, dict) and tur.get("type") == "create":
                rec["created"] = True
            rec["ops"].append(op)
            if is_err:
                failed_ops.append({"tool": name, "path": p, "ts": u["ts"], "error": one_line(res[1], 200)})
        elif name == "Bash":
            cmd = inp.get("command", "")
            if BASH_WRITE_RE.search(cmd) or BASH_REDIRECT_RE.search(QUOTED_RE.sub("''", cmd)):
                bash_writes.append({"ts": u["ts"], "cmd": one_line(cmd, 220),
                                    "move_or_delete": bool(BASH_MOVE_DELETE_RE.search(cmd)),
                                    "error": bool(is_err), "source": u["source"]})
        elif name.startswith("mcp__"):
            verb = name.split("__")[-1]
            if MCP_WRITE_RE.search(verb) and not MCP_READ_RE.search(verb):
                brief = {k: v for k, v in inp.items() if isinstance(v, (str, int, float, bool)) and len(str(v)) < 120}
                external.append({"ts": u["ts"], "tool": name, "args": one_line(json.dumps(brief), 200),
                                 "error": bool(is_err), "source": u["source"]})
        elif name == "Artifact" and inp.get("action", "publish") in ("publish", "delete"):
            external.append({"ts": u["ts"], "tool": "Artifact:" + inp.get("action", "publish"),
                             "args": one_line(inp.get("url") or inp.get("file_path") or "", 200),
                             "error": bool(is_err), "source": u["source"]})

    # Verify each file.
    rows = []
    for rp, rec in files.items():
        ok_ops = [o for o in rec["ops"] if o["ok"]]
        last_ok = max((o["ts"] for o in ok_ops if o["ts"]), default=None)
        notes, status = [], "OK"
        exists = os.path.exists(rp)
        mtime = os.path.getmtime(rp) if exists else None
        if not ok_ops:
            status = "FAILED" if any(not o["pending"] for o in rec["ops"]) else "UNCONFIRMED"
            notes.append("no successful write to this file this session")
        elif not exists:
            status = "MISSING-FILE"
            notes.append("file does not exist on disk")
        else:
            text, err = read_file_text(rp)
            if text is None:
                status = "UNREADABLE"
                notes.append(err)
            else:
                # Walk successful ops; a fragment absent from the file is fine only if
                # a LATER successful op in this session replaced it.
                missing = 0
                for i, o in enumerate(ok_ops):
                    later = ok_ops[i + 1:]
                    for fr in o["frags"]:
                        frag, kind = fr[0], fr[1]
                        if kind == "full":
                            if text == frag or (frag and frag in text):
                                continue
                            if later:
                                continue  # a later op changed it; judged by that op
                            missing += 1
                            notes.append("final Write content differs from what is on disk")
                            continue
                        if frag == "":
                            old = fr[2] if len(fr) > 2 else ""
                            if old and old in text and not later:
                                notes.append("deletion edit, but the removed text is still present (may be a second copy)")
                            continue
                        if frag in text:
                            continue
                        superseded = False
                        for lo in later:
                            if lo["tool"] == "Write":
                                superseded = True
                                break
                            for lf in lo["frags"]:
                                lold = lf[2] if len(lf) > 2 else ""
                                if lold and (frag in lold or lold in frag):
                                    superseded = True
                                    break
                            if superseded:
                                break
                        if not superseded:
                            missing += 1
                            notes.append("%s content not found: %s" % (o["tool"], one_line(frag, 70)))
                if missing:
                    status = "MISSING-CONTENT" if len(ok_ops) > 1 or rec["ops"][0]["tool"] != "Write" else "DIVERGED"
            if mtime is not None and last_ok is not None:
                if mtime < last_ok - MTIME_SLACK_S:
                    notes.append("mtime is OLDER than this session's last write (reverted or restored?)")
                    if status == "OK":
                        status = "WARN"
                elif mtime > last_ok + 60:
                    notes.append("modified %s after this session's last write (another process or session?)"
                                 % str(dt.timedelta(seconds=int(mtime - last_ok))))
                    if status == "OK":
                        status = "WARN"
        failed_n = sum(1 for o in rec["ops"] if not o["ok"] and not o["pending"])
        if failed_n and ok_ops:
            notes.append("%d failed op(s) on this file; later retries may cover them" % failed_n)
        rows.append({
            "status": status, "path": rec["path"], "created": rec["created"],
            "ops": len(rec["ops"]), "last_write": last_ok, "mtime": mtime,
            "sources": sorted(set(o["source"] for o in rec["ops"])), "notes": notes,
        })

    rank = {"MISSING-FILE": 0, "MISSING-CONTENT": 1, "DIVERGED": 2, "FAILED": 3, "UNREADABLE": 4,
            "UNCONFIRMED": 5, "WARN": 6, "OK": 7}
    rows.sort(key=lambda r: (rank.get(r["status"], 9), r["path"]))

    report = {
        "session": args.session, "transcript": main_t, "subagent_transcripts": subs,
        "window": {"first": t_first, "last": t_last},
        "files": rows, "failed_ops": failed_ops, "bash_writes": bash_writes, "external_writes": external,
        "counts": {s: sum(1 for r in rows if r["status"] == s) for s in rank},
    }

    if args.json:
        print(json.dumps(report, indent=2, default=str))
        return 0

    out = []
    out.append("# Session writes: %s" % (args.session or os.path.basename(main_t)))
    out.append("Transcript: %s%s" % (main_t, (" (+%d subagent transcripts)" % len(subs)) if subs else ""))
    out.append("Window: %s to %s (local)" % (fmt_ts(t_first), fmt_ts(t_last)))
    c = report["counts"]
    out.append("Files: %d total | %s" % (len(rows), ", ".join("%s %d" % (k, v) for k, v in c.items() if v)))
    out.append("")
    out.append("## Files written with Write/Edit/MultiEdit/NotebookEdit (%d)" % len(rows))
    if not rows:
        out.append("(none)")
    for r in rows:
        out.append("- [%s] %s  (%s, %d op%s, last write %s, mtime %s)%s" % (
            r["status"], r["path"], "created" if r["created"] else "edited", r["ops"],
            "" if r["ops"] == 1 else "s", fmt_ts(r["last_write"]), fmt_ts(r["mtime"]),
            "" if r["sources"] == ["main"] else " via " + ",".join(r["sources"])))
        for n in r["notes"]:
            out.append("    - %s" % n)
    out.append("")
    out.append("## Failed file-tool calls (%d)" % len(failed_ops))
    for f in failed_ops:
        out.append("- %s %s %s: %s" % (fmt_ts(f["ts"]), f["tool"], f["path"], f["error"]))
    if not failed_ops:
        out.append("(none)")
    out.append("")
    out.append("## Bash commands that may have written/moved/deleted files (%d) - review by hand" % len(bash_writes))
    for b in bash_writes:
        tag = "MOVE/DELETE " if b["move_or_delete"] else ""
        err = " [errored]" if b["error"] else ""
        out.append("- %s %s%s%s" % (fmt_ts(b["ts"]), tag, b["cmd"], err))
    if not bash_writes:
        out.append("(none)")
    out.append("")
    out.append("## External writes via MCP / Artifact (%d) - read back to verify" % len(external))
    for e in external:
        out.append("- %s %s %s%s" % (fmt_ts(e["ts"]), e["tool"], e["args"], " [errored]" if e["error"] else ""))
    if not external:
        out.append("(none)")
    print("\n".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
