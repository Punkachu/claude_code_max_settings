"""Tests for hooks/scripts/block-env-access.sh.

Run: python3 -m unittest discover tests   (pytest tests also works)
"""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "hooks" / "scripts" / "block-env-access.sh"
PLUGIN = Path(__file__).resolve().parent.parent / ".claude-plugin" / "plugin.json"
BASH = shutil.which("bash")
JQ = shutil.which("jq")

BLOCKED = [
    "cat .env",
    "cat ./.env",
    "cat /app/.env",
    "less ~/.env",
    "head -n 5 .env",
    "tail -f .env",
    "grep API_KEY .env",
    "source .env",
    ". .env",
    "cp .env /tmp/x",
    "cat .env.local",
    "cat .env.production",
    "cat '.env'",
    'cat ".env"',
    "python -c \"print(open('.env').read())\"",
    "ls && cat .env",
    "echo hi; cat config/.env | base64",
    ".env",
]

ALLOWED = [
    "ls -la",
    "npm test",
    "cat .env.example",
    "cp .env.example .env.sample",
    "cat .env.template",
    "node -e 'console.log(process.env.HOME)'",
    "cat .environment",
    "cat .envrc",
    "python -m venv .venv",
    "pip install python-dotenv",
    "echo $NODE_ENV",
    "cat prod.env",  # ponytail: only ".env*" names are covered, not "*.env"
    "",
]


def run(command, path=None):
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
    env = {"PATH": path} if path is not None else None
    return subprocess.run([BASH, str(SCRIPT)], input=payload, text=True, capture_output=True, timeout=10, env=env)


@unittest.skipUnless(BASH and JQ, "needs bash and jq")
class BlockEnvAccessTest(unittest.TestCase):
    def test_script_is_executable(self):
        self.assertTrue(os.access(SCRIPT, os.X_OK), f"chmod +x {SCRIPT}")

    def test_blocks_env_access(self):
        for command in BLOCKED:
            with self.subTest(command=command):
                proc = run(command)
                self.assertEqual(proc.returncode, 2)
                self.assertIn("Blocked", proc.stderr)

    def test_allows_everything_else(self):
        for command in ALLOWED:
            with self.subTest(command=command):
                proc = run(command)
                self.assertEqual((proc.returncode, proc.stderr), (0, ""))

    def test_template_does_not_hide_real_env(self):
        self.assertEqual(run("cp .env.example .env").returncode, 2)

    def test_missing_jq_fails_closed(self):
        with tempfile.TemporaryDirectory() as empty:
            proc = run("ls", path=empty)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("jq", proc.stderr)

    def test_plugin_registers_hook(self):
        hooks = json.loads(PLUGIN.read_text())["hooks"]["PreToolUse"]
        commands = [h["command"] for entry in hooks if entry["matcher"] == "Bash" for h in entry["hooks"]]
        self.assertEqual(commands, ["${CLAUDE_PLUGIN_ROOT}/hooks/scripts/block-env-access.sh"])


if __name__ == "__main__":
    unittest.main()
