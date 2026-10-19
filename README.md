# max_settings

A small Claude Code plugin with two hooks:

| Hook | Runs | Job |
|---|---|---|
| **Format on edit** | after every `Edit` / `Write` / `MultiEdit` | formats the file Claude just changed |
| **.env guardrail** | before `Bash`, `Read`, `Edit`, `Write`, `MultiEdit`, `NotebookEdit`, `Grep` | blocks any access to `.env` files |

## Install

```bash
./install.sh   # formatters (Homebrew) + .env deny rules in ~/.claude/settings.json
```

Then, in Claude Code:

```
/plugin marketplace add Punkachu/claude_code_max_settings
/plugin install max_settings@punkachu-tools
```

---

## 🎨 Format on edit

Picks a formatter by file extension and runs it on the edited file.

| Files | Formatter |
|---|---|
| `.ts` `.tsx` `.js` `.jsx` | `prettier` |
| `.go` | `gofmt` |
| `.dart` | `dart format` |
| `.py` `.pyi` | `ruff format` |
| `.c` `.h` `.cc` `.cpp` `.cxx` `.hpp` `.hh` `.hxx` | `clang-format` |
| `.kt` `.kts` | `ktlint -F` |
| `.swift` | `swiftformat` |

**Example:** Claude writes this…

```cpp
int main(){if(true){printf("hi");}return   0;}
```

…and the hook rewrites the file to this:

```cpp
int main() {
  if (true) {
    printf("hi");
  }
  return 0;
}
```

### ✅ Does
- Formats only the file that was edited, never the whole project.
- Uses your project's own config (`.prettierrc`, `pyproject.toml`, `.clang-format`, `.editorconfig`…).
- Stays silent when a formatter is missing or fails. The edit always goes through.

### ❌ Does not
- **Lint or fix code.** Formatting only. No `ruff check --fix` on purpose: it would delete imports Claude adds one edit before using them.
- **Download prettier.** If the project doesn't have it, nothing happens.
- **Format C/C++ without a `.clang-format`.** No config means the file is left alone.
- Touch any other file type (`.md`, `.json`, `.yaml`…).

### ⚠️ Limitations
- **Kotlin is slow.** `ktlint` runs on the JVM, about 1 s per edit.
- **`ruff format` always applies Black style**, even in projects that don't use it.
- Extensions are case-sensitive: `Main.PY` is skipped.

---

## 🔒 .env guardrail

Blocks Bash commands and Claude's file tools when they touch a `.env` file.

```text
cat .env                        ⛔ blocked
source .env                     ⛔ blocked
grep KEY config/.env.local      ⛔ blocked
python -c "open('.env')"        ⛔ blocked

cat .env.example                ✅ allowed
node -e 'process.env.HOME'      ✅ allowed
python -m venv .venv            ✅ allowed
```

```text
Read   /app/.env                ⛔ blocked
Write  /app/.env.local          ⛔ blocked
Grep   KEY  --glob ".env*"      ⛔ blocked

Read   /app/.env.example        ✅ allowed
Grep   ".env"  in /app/src      ✅ allowed   (searching for the text is fine)
```

Claude sees: `Blocked: access to .env files is prohibited.`

### ✅ Does
- Covers `.env` and every `.env.*` variant, at any depth, quoted or chained (`ls && cat .env`).
- Blocks reads **and writes**: Claude can't open, create or edit a `.env` file.
- Allows committed templates: `.env.example`, `.env.sample`, `.env.template`.
- Blocks every guarded call if `jq` is missing, rather than silently doing nothing.

### ❌ Does not
- Let Claude set up a `.env` for you. Copy `.env.example` yourself.
- Cover `*.env` names (`prod.env`) or other secret files (`.envrc`, `credentials.json`, `*.pem`).

### ⚠️ Limitations
- **It's a speed bump, not a vault.** It matches text, so `cat .e""nv`, base64 tricks or a script that reads the file get through. Keep real secrets out of the repo.
- `install.sh` also adds `Read(**/.env)` and `Read(**/.env.*)` deny rules as a backup. Those can't make exceptions, so with them installed the Read tool can't open `.env.example` either.

---

## Tests

```bash
python3 tests/run_all.py             # every suite; fails on any skip (use this in CI)
python3 tests/show_formatting.py     # before/after with your real formatters
```

## License

Apache-2.0
