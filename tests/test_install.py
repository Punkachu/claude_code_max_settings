"""Tests for install.sh's settings merge. Every tool is stubbed as already installed.

Run: python3 -m unittest discover tests
"""

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ["brew", "npx", "npm", "gofmt", "ruff", "clang-format", "ktlint", "swiftformat", "prettier", "dart"]
JQ = shutil.which("jq")
RULES = json.loads((ROOT / ".claude" / "settings.json").read_text())["permissions"]["deny"]


@unittest.skipUnless(JQ and shutil.which("bash"), "needs bash and jq")
class InstallTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name)
        bin_dir = self.home / "bin"
        bin_dir.mkdir()
        (bin_dir / "jq").symlink_to(JQ)
        for tool in TOOLS:
            stub = bin_dir / tool
            stub.write_text("#!/bin/sh\necho stub \"$@\" >&2; exit 1\n")  # any real install call would fail the run
            stub.chmod(0o755)
        self.env = {"HOME": str(self.home), "PATH": f"{bin_dir}:/usr/bin:/bin"}
        self.settings = self.home / ".claude" / "settings.json"

    def install(self):
        proc = subprocess.run(["bash", str(ROOT / "install.sh")], env=self.env, capture_output=True, text=True, timeout=30)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("install ", proc.stdout)
        return json.loads(self.settings.read_text())

    def test_creates_settings(self):
        self.assertEqual(self.install(), {"permissions": {"deny": RULES}})

    def test_merges_without_losing_user_settings_and_is_idempotent(self):
        self.settings.parent.mkdir()
        user = {"model": "opus", "permissions": {"allow": ["Bash(ls)"], "deny": ["Bash(rm -rf *)", RULES[0]]}}
        self.settings.write_text(json.dumps(user))
        self.install()
        result = self.install()
        self.assertEqual(result["model"], "opus")
        self.assertEqual(result["permissions"]["allow"], ["Bash(ls)"])
        self.assertEqual(result["permissions"]["deny"], ["Bash(rm -rf *)", RULES[0], *RULES[1:]])
        self.assertEqual(json.loads((self.settings.parent / "settings.json.bak").read_text())["model"], "opus")

    def test_invalid_settings_are_left_untouched(self):
        self.settings.parent.mkdir()
        self.settings.write_text("{not json")
        proc = subprocess.run(["bash", str(ROOT / "install.sh")], env=self.env, capture_output=True, text=True, timeout=30)
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(self.settings.read_text(), "{not json")


if __name__ == "__main__":
    unittest.main()
