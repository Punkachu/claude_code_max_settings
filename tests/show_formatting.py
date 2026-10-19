"""Visual check: run the hook with the REAL formatters on messy code, print before/after.

Run: python3 tests/show_formatting.py
Formatters that aren't installed are reported as SKIP.
"""

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "hooks" / "scripts" / "format-changed-file.sh"

# file name -> (formatter it needs, messy source)
SAMPLES = {
    "app.ts": ("npx", "const  x={a:1,b:[1,2,3]}\nfunction f( y ){return y*2}\n"),
    "main.go": ("gofmt", "package main\nimport \"fmt\"\nfunc main(){\nfmt.Println( \"hi\" )\n}\n"),
    "main.dart": ("dart", "void main(){print( 'hi' );\nvar x=[1,2,3];}\n"),
    "app.py": ("ruff", "def f( a,b ):\n  return {'a':a,'b':b}\nx=[1,2 ,3]\n"),
    "main.cpp": ("clang-format", "#include <cstdio>\nint main(){if(true){printf(\"hi\");}return   0;}\n"),
    "Main.kt": ("ktlint", "fun main(){\nval x=listOf(1,2,3)\n    println( x )\n}\n"),
    "Main.swift": ("swiftformat", "func main(){\nlet x=[1,2,3]\n    print( x )\n}\n"),
}


def main():
    with tempfile.TemporaryDirectory() as tmp:
        # clang-format only formats projects that opt in with a .clang-format
        Path(tmp, ".clang-format").write_text("BasedOnStyle: LLVM\n")
        for name, (tool, src) in SAMPLES.items():
            print(f"===== {name} ({tool}) " + "=" * 40)
            if not shutil.which(tool):
                print("SKIP: not installed\n")
                continue
            path = Path(tmp, name)
            path.write_text(src)
            payload = json.dumps({"tool_input": {"file_path": str(path)}})
            subprocess.run(["bash", str(SCRIPT)], input=payload, text=True, capture_output=True, timeout=120)
            after = path.read_text()
            print("--- before\n" + src + "--- after\n" + after)
            print("RESULT:", "UNCHANGED (formatter failed?)" if after == src else "formatted", "\n")


if __name__ == "__main__":
    main()
