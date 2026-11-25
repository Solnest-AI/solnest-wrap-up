"""install.sh: installs the skill into a (fake) home, writes the launcher, keeps the user's
own references/homes.md on a second run, and refuses to overwrite a different skill.
Offline: it installs from this copy of the repo, or from a local archive."""
import os
import pathlib
import shutil
import subprocess
import tarfile
import tempfile
import unittest

REPO = pathlib.Path(__file__).resolve().parent.parent
BASH = shutil.which("bash")
MINE = "# Where things live\n\n## Your setup\n\n- Notes system: my own vault\n"


@unittest.skipUnless(BASH, "needs bash")
class InstallTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = pathlib.Path(self.tmp.name) / "home"
        self.home.mkdir()
        self.dest = self.home / ".claude" / "skills" / "wrap-up"

    def run_install(self, script=None, stdin=None, **extra):
        env = dict(os.environ, HOME=str(self.home), **extra)
        args = [BASH, str(script)] if script else [BASH]
        return subprocess.run(args, env=env, capture_output=True, text=True, timeout=300,
                              stdin=stdin or subprocess.DEVNULL, cwd=self.tmp.name)

    def test_installs_and_a_second_run_keeps_homes(self):
        r = self.run_install(REPO / "install.sh")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("[ok] scanner", r.stdout)
        for rel in ("SKILL.md", "VERSION", "bin/py", "scripts/session_writes.py", "scripts/update.py",
                    "scripts/solnest_autoupdate.py", "references/homes.md"):
            self.assertTrue((self.dest / rel).is_file(), rel)
        self.assertEqual((self.dest / "VERSION").read_text(), (REPO / "VERSION").read_text())
        h = subprocess.run([str(self.dest / "bin" / "py"), str(self.dest / "scripts" / "session_writes.py"), "--help"],
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(h.returncode, 0, h.stderr)

        (self.dest / "references" / "homes.md").write_text(MINE, encoding="utf-8")
        (self.dest / "my-notes.md").write_text("mine\n", encoding="utf-8")
        r = self.run_install(REPO / "install.sh")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("kept your own setup notes", r.stdout)
        self.assertEqual((self.dest / "references" / "homes.md").read_text(), MINE)
        self.assertEqual((self.dest / "my-notes.md").read_text(), "mine\n")

    def test_piped_install_from_an_archive(self):
        """The `curl ... | bash` path: no local repo, the skill comes from an archive."""
        archive = pathlib.Path(self.tmp.name) / "main.tar.gz"
        with tarfile.open(archive, "w:gz") as tar:
            tar.add(REPO / "VERSION", "solnest-wrap-up-main/VERSION")
            tar.add(REPO / "skill", "solnest-wrap-up-main/skill",
                    filter=lambda t: None if "__pycache__" in t.name else t)
        with open(REPO / "install.sh", "rb") as script:
            r = self.run_install(stdin=script, WRAP_UP_ARCHIVE_URL=archive.as_uri())
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("downloading the skill", r.stdout)
        self.assertTrue((self.dest / "SKILL.md").is_file())
        self.assertEqual((self.dest / "VERSION").read_text(), (REPO / "VERSION").read_text())

    def test_refuses_a_different_skill(self):
        self.dest.mkdir(parents=True)
        (self.dest / "SKILL.md").write_text("---\nname: something-else\n---\n", encoding="utf-8")
        r = self.run_install(REPO / "install.sh")
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
        self.assertEqual((self.dest / "SKILL.md").read_text(), "---\nname: something-else\n---\n")
        self.assertFalse((self.dest / "scripts").exists())


if __name__ == "__main__":
    unittest.main()
