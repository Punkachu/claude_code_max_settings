# max_settings

A small Claude Code plugin with three hooks:

| Hook | Runs | Job |
|---|---|---|
| **Format on edit** | after every `Edit` / `Write` / `MultiEdit` | formats the file Claude just changed |
| **.env guardrail** | before `Bash`, `Read`, `Edit`, `Write`, `MultiEdit`, `NotebookEdit`, `Grep` | blocks any access to `.env` files |
| **Dangerous-command guardrail** | before every `Bash` command | blocks commands that destroy data, history or infrastructure |

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

## 🛑 Dangerous-command guardrail

Stops Claude from running commands that can't be undone. When one is blocked, Claude is told **which rule fired and what to do instead**, so it switches to the safer command rather than retrying:

```text
$ git reset --hard
Blocked [git-reset-hard]: git reset --hard discards uncommitted work. Use git stash,
or git reset --soft / --mixed. If it's really needed, ask the user to run it themselves.
```

### What happens when a command is blocked

1. The command **does not run**. Nothing on disk, in git or in the cloud changes.
2. Claude reads the message and usually retries with the suggested alternative, e.g. `git stash` instead of `git reset --hard`.
3. If there is no safe alternative, Claude asks you. **You** can then run the command yourself in your own terminal: the guardrail only checks commands Claude runs.

### Rules

**📁 Files and disks**

| Rule | Blocked | Still allowed | Claude is told |
|---|---|---|---|
| `rm-critical-path` | `rm -rf /` · `~` · `$HOME` · `.` · `..` · `*` · `.git` · `/etc`, `/usr`… · `"$DIR/"*` | `rm -rf ./build` · `node_modules` · `/tmp/x` · `~/projects/old` | delete the specific paths |
| `rm-no-preserve-root` | `rm --no-preserve-root …` | | — |
| `find-delete-root` | `find / … -delete` · `find ~ -exec rm` | `find . -name '*.pyc' -delete` | run it from the project with a narrow `-name` |
| `disk-wipe` | `mkfs` · `wipefs` · `dd of=/dev/sda` · `> /dev/nvme0n1` · `shred /dev/…` | `dd of=./disk.img` · `> /dev/null` | — |
| `fork-bomb` | `:(){ :\|:& };:` | | — |
| `chmod-777` | `chmod -R 777 …` | `chmod +x script.sh` · `chmod 644 file` | grant the specific permission |
| `chown-chmod-root` | `chown -R … /` · `chmod -R … ~` | `chown me file.txt` | — |

> `rm -rf "$DIR/"` is blocked on purpose: if `$DIR` is empty, it becomes `rm -rf /`.

**🌿 Git**

| Rule | Blocked | Still allowed | Claude is told |
|---|---|---|---|
| `git-force-push` | `push --force` · `push -f` · `push origin +main` | `push --force-with-lease` | use `--force-with-lease`, never on main/master without asking |
| `git-delete-main` | `push origin --delete main` · `push origin :master` | deleting any other branch | — |
| `git-reset-hard` | `reset --hard` (any target) | `reset --soft` · `reset --mixed` · `reset HEAD file` | use `git stash` |
| `git-clean-force` | `clean -f` · `-fd` · `-xdf` | `clean -n` (dry run) | run `git clean -n` and show you the list |
| `git-discard-all` | `checkout .` · `checkout -- .` · `restore .` | `checkout -- file` · `restore --staged .` | restore specific files, or stash |
| `git-branch-force-delete` | `branch -D x` | `branch -d x` (refuses unless merged) | use `git branch -d` |
| `git-stash-clear` | `stash clear` | `stash drop stash@{n}` | drop specific entries |
| `git-history-rewrite` | `filter-branch` · `filter-repo` · `reflog expire` | | — |
| `git-no-verify` | `commit --no-verify` · `push --no-verify` · `merge --no-verify` | | fix what the hook reports |

**🗄️ Databases**

Matched in any case (`drop table`, `DROP TABLE`, `Drop Table`), whatever the client (`psql`, `mysql`, `sqlite3`, `redis-cli`, `mongosh`…).

| Rule | Blocked | Still allowed | Claude is told |
|---|---|---|---|
| `sql-drop` | `DROP TABLE` · `DATABASE` · `SCHEMA` · `COLLECTION` | `DROP INDEX` · `SELECT …` | write a migration and let you apply it |
| `sql-truncate` | `TRUNCATE [TABLE] x` | `truncate -s 0 app.log` (the Linux command) | — |
| `sql-delete-all` | `DELETE FROM users` (no `WHERE`) | `DELETE FROM users WHERE id = 1` | add a `WHERE` clause |
| `nosql-wipe` | `FLUSHALL` · `FLUSHDB` · `db.dropDatabase()` · `db.x.drop()` | | — |

**☁️ Infrastructure**

| Rule | Blocked | Still allowed | Claude is told |
|---|---|---|---|
| `k8s-mass-delete` | `kubectl delete ns x` · `namespace x` · `… --all` | `kubectl delete pod web-123` · `kubectl get …` | delete named resources after `kubectl get` |
| `terraform-destroy` | `terraform destroy` · `apply -auto-approve` (and `tofu`) | `terraform plan` · `plan -destroy` · `apply` (asks to confirm) | run `terraform plan` and show you |
| `cloud-delete` | `aws s3 rm --recursive` · `aws s3 rb --force` · `gcloud projects delete` · `az group delete` | `aws s3 ls` · `aws s3 rm s3://b/one-file` | — |
| `docker-wipe` | `system prune -a` · `--volumes` · `volume prune` · `volume rm` | `docker system prune` · `docker rm web` | remove named containers or images |

**🌐 Remote scripts, system, publishing**

| Rule | Blocked | Still allowed | Claude is told |
|---|---|---|---|
| `pipe-to-shell` | `curl … \| sh` · `wget … \| bash` · `bash <(curl …)` · `sh -c "$(curl …)"` | `curl -o install.sh` · `curl … \| jq` · `\| python3 -m json.tool` | download it, show you, then run it |
| `system-power` | `shutdown` · `reboot` · `halt` · `poweroff` · `kill -9 -1` | `kill -9 12345` | — |
| `publish-package` | `npm`/`pnpm`/`yarn publish` · `cargo publish` · `dart`/`flutter pub publish` · `twine upload` · `gem push` | **any of those with `--dry-run`** · `npm pack` | check with `--dry-run`, then let you publish |

> `npm publish --dry-run && npm publish` is still blocked: each command in a chain is checked on its own.

### ✅ Does
- Checks every Bash command Claude runs, including chains (`a && b`, `a; b`, `a | b`) and `sudo`.
- Sees through simple disguises: `"rm" -rf '/'`, `\rm`, `/bin/rm`.
- Blocks every command if `jq` is missing, rather than silently doing nothing.
- Adds about 8 ms per command.

### ❌ Does not
- Check commands **you** run in your own terminal.
- Check what scripts do: `./cleanup.sh` runs even if it contains `rm -rf /`.
- Catch `UPDATE` without `WHERE` (a pattern can't check that something is missing).
- Cover `helm uninstall`, `docker push`, or deleting cloud resources other than those above.

### ⚠️ Limitations
- **False positives.** Quotes are ignored so that `"rm" -rf /` can't sneak past. As a result, harmless commands that only *mention* a dangerous one are blocked too:
  ```text
  grep -r 'drop table' docs/                        ⛔ blocked
  git commit -m 'stop using git push --force'       ⛔ blocked
  echo 'never run rm -rf /'                         ⛔ blocked
  ```
  Claude will ask you to run these, or reword them (for example, a commit message without the command).
- **Easy to get around on purpose:** `x=rm; $x -rf /`, base64, or writing a script first. It stops **mistakes**, not someone trying to cause damage.
- **A noisy rule?** Delete just that `rule …` line in `hooks/scripts/block-dangerous-commands.sh`. Don't turn off the whole hook: you'd lose all 27 rules.

---

## Tests

```bash
python3 tests/run_all.py             # every suite; fails on any skip (use this in CI)
python3 tests/show_formatting.py     # before/after with your real formatters
```

## License

Apache-2.0
