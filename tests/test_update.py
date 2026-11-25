"""scripts/update.py: installs only a published release into the skill folder, keeps the
user's own setup notes (references/homes.md), bin/ and their own files, and --undo puts
the old version back. Offline: releases are read from a local folder (WRAP_UP_RELEASE_DIR)."""
import io
import os
import pathlib
import sys
import tarfile
import tempfile
import unittest
from unittest import mock

SCRIPTS = pathlib.Path(__file__).resolve().parent.parent / "skill" / "wrap-up" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import update  # noqa: E402

FAKE_ENV = "SOME_KEY=fake_test_" + "0" * 24 + "\n"   # a made-up value, never a real key
MY_HOMES = "# Where things live\n\n## Your setup\n\n- Notes system: my own vault at ~/notes\n"


def tarball(folder, version, files, top=None):
    """A GitHub-style source tarball: one top folder, the skill under skill/wrap-up/."""
    top = top or f"solnest-wrap-up-{version}"
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        def add(rel, data):
            info = tarfile.TarInfo(f"{top}/{rel}")
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
        add("VERSION", f"{version}\n".encode())
        add("README.md", b"repo readme, not installed\n")
        for rel, text in files.items():
            add(f"skill/wrap-up/{rel}", text.encode())
    (pathlib.Path(folder) / f"v{version}.tar.gz").write_bytes(buf.getvalue())


class UpdateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = pathlib.Path(self.tmp.name)
        self.rel = base / "releases"
        self.rel.mkdir()
        self.root = base / "skills" / "wrap-up"
        self.root.mkdir(parents=True)
        env = mock.patch.dict(os.environ, {update.LOCAL_RELEASES: str(self.rel)})
        env.start()
        self.addCleanup(env.stop)
        self.addCleanup(self.tmp.cleanup)
        old = {"SKILL.md": "old skill\n", "scripts/session_writes.py": "old scanner\n",
               "scripts/dropped.py": "gone next\n", "references/homes.md": "default homes 1.0.0\n"}
        tarball(self.rel, "1.0.0", old)
        for rel, text in old.items():
            (self.root / rel).parent.mkdir(parents=True, exist_ok=True)
            (self.root / rel).write_text(text, encoding="utf-8")
        (self.root / "VERSION").write_text("1.0.0\n", encoding="utf-8")
        (self.root / "references" / "homes.md").write_text(MY_HOMES, encoding="utf-8")   # the user edited it
        (self.root / ".env").write_text(FAKE_ENV, encoding="utf-8")
        (self.root / "bin").mkdir()
        (self.root / "bin" / "py").write_text("fake launcher\n", encoding="utf-8")
        (self.root / "my-notes.md").write_text("mine\n", encoding="utf-8")

    def _new_release(self):
        tarball(self.rel, "1.1.0", {"SKILL.md": "new skill\n", "scripts/session_writes.py": "new scanner\n",
                                    "scripts/new.py": "brand new\n", "bin/py": "release must not win\n",
                                    "references/homes.md": "default homes 1.1.0\n",
                                    ".env": "SOME_KEY=from_release\n"})

    def test_update_keeps_user_files_and_undo_goes_back(self):
        self._new_release()
        r = update.update(self.root)
        self.assertEqual(r["status"], "updated")
        self.assertEqual((self.root / "VERSION").read_text().strip(), "1.1.0")
        self.assertEqual((self.root / "SKILL.md").read_text(), "new skill\n")
        self.assertTrue((self.root / "scripts" / "new.py").is_file())
        self.assertFalse((self.root / "scripts" / "dropped.py").exists())   # shipped by 1.0.0, not 1.1.0
        self.assertFalse((self.root / "README.md").exists())                # repo files are not installed
        self.assertEqual((self.root / "references" / "homes.md").read_text(), MY_HOMES)
        self.assertEqual((self.root / ".env").read_text(), FAKE_ENV)
        self.assertEqual((self.root / "bin" / "py").read_text(), "fake launcher\n")
        self.assertEqual((self.root / "my-notes.md").read_text(), "mine\n")
        self.assertEqual(update.update(self.root)["status"], "current")

        update.undo(self.root)
        self.assertEqual((self.root / "VERSION").read_text().strip(), "1.0.0")
        self.assertEqual((self.root / "SKILL.md").read_text(), "old skill\n")
        self.assertTrue((self.root / "scripts" / "dropped.py").is_file())
        self.assertFalse((self.root / "scripts" / "new.py").exists())
        self.assertEqual((self.root / "references" / "homes.md").read_text(), MY_HOMES)
        self.assertEqual((self.root / ".env").read_text(), FAKE_ENV)
        self.assertEqual((self.root / "my-notes.md").read_text(), "mine\n")

    def test_manifest_lists_what_shipped_and_never_the_user_files(self):
        self._new_release()
        update.update(self.root)
        listed = set(update.load_manifest(self.root))
        self.assertEqual(listed, {"VERSION", "SKILL.md", "scripts/session_writes.py", "scripts/new.py"})
        # the next release drops scripts/new.py: the manifest is what gets it removed
        tarball(self.rel, "1.2.0", {"SKILL.md": "newer skill\n", "scripts/session_writes.py": "newer scanner\n"})
        r = update.update(self.root)
        self.assertEqual(r["removed"], ["scripts/new.py"])
        self.assertFalse((self.root / "scripts" / "new.py").exists())
        self.assertEqual((self.root / "references" / "homes.md").read_text(), MY_HOMES)
        self.assertEqual((self.root / "my-notes.md").read_text(), "mine\n")

    def test_missing_homes_is_put_back_from_the_release(self):
        (self.root / "references" / "homes.md").unlink()
        self._new_release()
        update.update(self.root)
        self.assertEqual((self.root / "references" / "homes.md").read_text(), "default homes 1.1.0\n")

    def test_refuses_a_git_checkout(self):
        (self.root.parent.parent / "skill").mkdir()
        clone_skill = self.root.parent.parent / "skill" / "wrap-up"
        clone_skill.mkdir()
        (self.root.parent.parent / ".git").mkdir()
        tarball(self.rel, "1.1.0", {"SKILL.md": "new\n"})
        with self.assertRaises(update.UpdateError):
            update.update(clone_skill)

    def test_unsafe_release_changes_nothing(self):
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tar:
            for name in ("top/VERSION", "../evil"):
                info = tarfile.TarInfo(name)
                info.size = 1
                tar.addfile(info, io.BytesIO(b"x"))
        (self.rel / "v1.1.0.tar.gz").write_bytes(buf.getvalue())
        with self.assertRaises(update.UpdateError):
            update.update(self.root)
        self.assertEqual((self.root / "VERSION").read_text().strip(), "1.0.0")
        self.assertEqual((self.root / "SKILL.md").read_text(), "old skill\n")

    def test_no_release_yet_is_a_plain_error(self):
        for p in self.rel.glob("*"):
            p.unlink()
        with self.assertRaises(update.UpdateError):
            update.update(self.root)


if __name__ == "__main__":
    unittest.main()
