"""Tests for hooks/scripts/block-env-access.sh (Bash commands and file tools).

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


# (tool, tool_input) for Claude's file tools
FILE_BLOCKED = [
    ("Read", {"file_path": "/app/.env"}),
    ("Read", {"file_path": ".env"}),
    ("Read", {"file_path": "/app/config/.env.production"}),
    ("Edit", {"file_path": "/app/.env", "old_string": "a", "new_string": "b"}),
    ("Write", {"file_path": "/app/.env.local", "content": "KEY=1"}),
    ("MultiEdit", {"file_path": "/app/.env", "edits": []}),
    ("NotebookEdit", {"notebook_path": "/app/.env", "new_source": "x"}),
    ("Grep", {"pattern": "KEY", "path": "/app/.env"}),
    ("Grep", {"pattern": "KEY", "glob": ".env*"}),
    ("Grep", {"pattern": "KEY", "path": "/app", "glob": "**/.env"}),
]

FILE_ALLOWED = [
    ("Read", {"file_path": "/app/.env.example"}),
    ("Write", {"file_path": "/app/.env.template", "content": "KEY="}),
    ("Read", {"file_path": "/app/.environment"}),
    ("Read", {"file_path": "/app/.envrc"}),
    ("Read", {"file_path": "/app/src/env.ts"}),
    ("Edit", {"file_path": "/app/.venv/lib/site.py", "old_string": "a", "new_string": "b"}),
    ("Grep", {"pattern": ".env", "path": "/app/src"}),  # searching FOR the text ".env" is fine
    ("Read", {}),
]


def run(command, path=None, tool="Bash", tool_input=None):
    payload = json.dumps({"tool_name": tool, "tool_input": tool_input or {"command": command}})
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

    def test_blocks_file_tools_on_env(self):
        for tool, tool_input in FILE_BLOCKED:
            with self.subTest(tool=tool, tool_input=tool_input):
                proc = run(None, tool=tool, tool_input=tool_input)
                self.assertEqual(proc.returncode, 2)
                self.assertIn("Blocked", proc.stderr)

    def test_allows_file_tools_elsewhere(self):
        for tool, tool_input in FILE_ALLOWED:
            with self.subTest(tool=tool, tool_input=tool_input):
                proc = run(None, tool=tool, tool_input=tool_input or {"file_path": ""})
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
        self.assertEqual(
            [(entry["matcher"], h["command"]) for entry in hooks for h in entry["hooks"]],
            [("Bash|Read|Edit|Write|MultiEdit|NotebookEdit|Grep", "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/block-env-access.sh")],
        )

    def test_marketplace_lists_plugin_by_its_name(self):
        market = json.loads((PLUGIN.parent / "marketplace.json").read_text())
        self.assertEqual([p["name"] for p in market["plugins"]], [json.loads(PLUGIN.read_text())["name"]])


if __name__ == "__main__":
    unittest.main()
