# Changelog

## 1.0.0

First release as its own GitHub repo.
- Install by pasting the repo link into Claude Code and saying "set this up".
- The skill installs to `~/.claude/skills/wrap-up`. Setup finds Python (or installs it) and the skill always uses that one.
- Updates install themselves once a day, in the background, from published releases only. If a new release does not start, the old one is put back by itself.
- An update never touches your own setup notes (`references/homes.md`) or any file you added. Changes you ask for are kept in `~/.solnest/wrap-up/my-instructions.md`.
