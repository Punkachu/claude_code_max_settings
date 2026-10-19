"""Tests for hooks/scripts/format-changed-file.sh.

Every formatter is replaced by a stub on PATH that logs its argv, so the suite
runs without prettier, ruff, clang-format, ktlint, etc. installed.

Run: python3 -m unittest discover tests   (pytest tests also works)
"""

import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "hooks" / "scripts" / "format-changed-file.sh"
BASH = shutil.which("bash")
JQ = shutil.which("jq")

PRETTIER = ["npx", "--no-install", "prettier", "--write"]
CLANG = ["clang-format", "-i", "--fallback-style=none"]

# extension -> formatter argv expected before the file path
RULES = {
    ".ts": PRETTIER,
    ".tsx": PRETTIER,
    ".js": PRETTIER,
    ".jsx": PRETTIER,
    ".go": ["gofmt", "-w"],
    ".dart": ["dart", "format"],
    ".py": ["ruff", "format"],
    ".pyi": ["ruff", "format"],
    ".c": CLANG,
    ".h": CLANG,
    ".cc": CLANG,
    ".cpp": CLANG,
    ".cxx": CLANG,
    ".hpp": CLANG,
    ".hh": CLANG,
    ".hxx": CLANG,
    ".kt": ["ktlint", "-F"],
    ".kts": ["ktlint", "-F"],
    ".swift": ["swiftformat", "--quiet"],
}

FORMATTERS = {argv[0] for argv in RULES.values()}

# Logs "name<TAB>arg1<TAB>arg2..." per call, using only sh builtins.
STUB = """#!/bin/sh
line=${0##*/}
for a in "$@"; do line="$line\t$a"; done
printf '%s\\n' "$line" >> "$FORMAT_LOG"
exit "${STUB_EXIT:-0}"
"""


def script_extensions():
    """Every extension the script's case statement matches."""
    patterns = re.findall(r"^\s*(\*\.[^)\s]+)\)", SCRIPT.read_text(), re.M)
    return {p[1:] for pattern in patterns for p in pattern.split("|")}


@unittest.skipUnless(BASH and JQ, "needs bash and jq")
class FormatChangedFileTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.bin = self.tmp / "bin"
        self.bin.mkdir()
        self.log = self.tmp / "calls.log"
        # PATH holds only jq and the stubs, so real formatters can't leak in.
        (self.bin / "jq").symlink_to(JQ)
        for name in FORMATTERS:
            stub = self.bin / name
            stub.write_text(STUB)
            stub.chmod(0o755)

    def run_hook(self, stdin, **env):
        proc = subprocess.run(
            [BASH, str(SCRIPT)],
            input=stdin,
            text=True,
            capture_output=True,
            timeout=10,
            env={"PATH": str(self.bin), "FORMAT_LOG": str(self.log), **env},
        )
        calls = [line.split("\t") for line in self.log.read_text().splitlines()] if self.log.exists() else []
        self.log.unlink(missing_ok=True)
        return proc.returncode, calls

    def edit(self, name, **env):
        path = self.tmp / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x")
        payload = {"tool_name": "Edit", "tool_input": {"file_path": str(path), "old_string": "a", "new_string": "b"}}
        return str(path), *self.run_hook(json.dumps(payload), **env)

    def test_script_is_executable(self):
        self.assertTrue(os.access(SCRIPT, os.X_OK), f"chmod +x {SCRIPT}")

    def test_every_script_rule_has_a_test(self):
        self.assertEqual(script_extensions(), set(RULES))

    def test_each_extension_runs_its_formatter(self):
        for ext, argv in RULES.items():
            with self.subTest(ext=ext):
                path, code, calls = self.edit(f"src/main{ext}")
                self.assertEqual(code, 0)
                self.assertEqual(calls, [argv + [path]])

    def test_write_tool_payload(self):
        path = self.tmp / "app.dart"
        path.write_text("x")
        payload = {"tool_name": "Write", "tool_input": {"file_path": str(path), "content": "x"}}
        self.assertEqual(self.run_hook(json.dumps(payload)), (0, [["dart", "format", str(path)]]))

    def test_unmatched_files_are_left_alone(self):
        for name in ["README.md", "data.json", "Makefile", "pubspec.yaml", "main.go.orig", "app.dart.bak", "x.py~", "Main.PY"]:
            with self.subTest(name=name):
                self.assertEqual(self.edit(name)[1:], (0, []))

    def test_path_with_spaces_is_one_argument(self):
        path, code, calls = self.edit("my dir/main file.py")
        self.assertEqual((code, calls), (0, [["ruff", "format", path]]))

    def test_bad_input_is_a_noop(self):
        missing = json.dumps({"tool_input": {"file_path": str(self.tmp / "gone.py")}})
        for stdin in ["", "not json", "{}", '{"tool_input": {}}', '{"tool_input": {"file_path": null}}', missing]:
            with self.subTest(stdin=stdin):
                self.assertEqual(self.run_hook(stdin), (0, []))

    def test_failing_formatter_does_not_fail_the_hook(self):
        path, code, calls = self.edit("broken.swift", STUB_EXIT="1")
        self.assertEqual((code, calls), (0, [["swiftformat", "--quiet", path]]))

    def test_missing_formatter_does_not_fail_the_hook(self):
        (self.bin / "ktlint").unlink()
        self.assertEqual(self.edit("Build.kt")[1:], (0, []))


if __name__ == "__main__":
    unittest.main()
