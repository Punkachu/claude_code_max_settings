#!/usr/bin/env bash
# PreToolUse hook (Bash): block commands that destroy data, history or infrastructure.
# Exit 2 blocks the command; stderr tells Claude which rule fired and what to do instead.
# Portable to macOS's bash 3.2: POSIX classes only, no \s or \b.

# Fail closed: without jq we can't inspect the command.
command -v jq >/dev/null || { echo "Blocked: jq is required by the dangerous-command guardrail." >&2; exit 2; }

cmd=$(jq -r '.tool_input.command // empty')
# Drop quotes and backslashes so "rm" -rf '/', \rm and r''m all read as rm -rf /.
cmd=${cmd//[\"\'\\]/}

S='[[:space:]]'
B='(^|[[:space:];&|(`/])'  # start of a command word
E='([[:space:];&|)]|$)'    # end of a word
A='([^;&|]*[[:space:]])?'  # other arguments within the same command

rule() { # id, i (ignore case) or -, regex, what to do instead
  if [ "$2" = i ]; then shopt -s nocasematch; else shopt -u nocasematch; fi
  if [[ $cmd =~ $3 ]]; then
    echo "Blocked [$1]: $4 If it's really needed, ask the user to run it themselves." >&2
    exit 2
  fi
}

# --- Filesystem ---
rule rm-critical-path - "${B}rm${S}${A}-[[:alnum:]-]*[rR][^;&|]*${S}"'(/|/\*|~/?\*?|\$\{?HOME\}?/?\*?|\.\.?/?\*?|\*|\.git/?|\$\{?[[:alnum:]_]+\}?/\*?|/(bin|boot|dev|etc|home|lib|lib64|opt|root|sbin|srv|usr|var|System|Users|Applications|Library)/?\*?)'"$E" \
  "Recursive delete of a root, home, system, whole-project or .git path (or \$VAR/ that may be empty). Delete the specific paths, e.g. rm -rf ./build."
rule rm-no-preserve-root - "${B}rm${S}${A}--no-preserve-root" \
  "--no-preserve-root disables rm's last safety net."
rule find-delete-root - "${B}find${S}+"'(/|~/?|\$\{?HOME\}?/?)'"${E}[^;&|]*(-delete|-exec${S}+rm)" \
  "find -delete from / or home. Run it from the project directory with a narrow -name filter."
rule disk-wipe - "${B}(mkfs(\.[[:alnum:]]+)?|wipefs)${E}|(of=|>${S}*)/dev/(sd|hd|vd|xvd|nvme|disk|mmcblk)|${B}shred${S}[^;&|]*/dev/" \
  "Formats or overwrites a disk."
rule fork-bomb - ":\(\)${S}*\{" \
  "Fork bomb."
rule chmod-777 - "${B}chmod${S}+(-[[:alnum:]]*R[[:alnum:]]*|--recursive)${S}+0?777" \
  "Recursive 777 makes everything world-writable. Grant the specific permission needed, e.g. chmod u+x script.sh."
rule chown-chmod-root - "${B}ch(own|mod)${S}+(-[[:alnum:]]*R[[:alnum:]]*|--recursive)${S}+[^[:space:]]+${S}+"'(/|~/?|\$\{?HOME\}?/?)'"$E" \
  "Recursive ownership or permission change on / or home."

# --- Git ---
rule git-force-push - "${B}git${S}${A}push${S}${A}(--force|-[[:alnum:]]*f[[:alnum:]]*)${E}|${B}git${S}${A}push${S}[^;&|]*${S}\+[^[:space:]]" \
  "Force push rewrites shared history. Use git push --force-with-lease, and never on main/master without asking."
rule git-delete-main - "${B}git${S}${A}push${S}[^;&|]*(${S}(--delete|-d)${S}+[^;&|]*|${S}:)(main|master)${E}" \
  "Deletes the remote main/master branch."
rule git-reset-hard - "${B}git${S}${A}reset${S}${A}--hard${E}" \
  "git reset --hard discards uncommitted work. Use git stash, or git reset --soft / --mixed."
rule git-clean-force - "${B}git${S}${A}clean${S}${A}(-[[:alnum:]]*f|--force)" \
  "git clean -f deletes untracked files for good. Run git clean -n first and show the user the list."
rule git-discard-all - "${B}git${S}${A}(checkout|restore)${S}+(--${S}+)?\.${E}" \
  "Discards every uncommitted change. Restore specific files, or git stash."
rule git-branch-force-delete - "${B}git${S}${A}branch${S}${A}(-D|--delete${S}+--force|-d${S}+-f)${E}" \
  "git branch -D drops unmerged commits. Use git branch -d, which refuses unless merged."
rule git-stash-clear - "${B}git${S}${A}stash${S}+clear${E}" \
  "Deletes every stash. Drop specific entries with git stash drop stash@{n}."
rule git-history-rewrite - "${B}git${S}${A}(filter-branch|filter-repo|reflog${S}+expire)${E}" \
  "Rewrites or expires history."
rule git-no-verify - "${B}git${S}${A}(commit|push|merge)${S}${A}--no-verify${E}" \
  "--no-verify skips the repo's hooks. Fix what the hook reports instead."

# --- Databases ---
rule sql-drop i "${B}drop${S}+(table|database|schema|collection)${E}" \
  "DROP destroys data. Write a migration and let the user apply it."
rule sql-truncate i "${B}truncate${S}+(table${S}+)?[[:alpha:]_]" \
  "TRUNCATE deletes every row."
rule sql-delete-all i "${B}delete${S}+from${S}+[^[:space:];]+${S}*(;|$)" \
  "DELETE without WHERE deletes every row. Add a WHERE clause."
rule nosql-wipe i "${B}(flushall|flushdb)${E}|dropDatabase\(|\.drop\(\)" \
  "Wipes a Redis or MongoDB database."

# --- Infrastructure ---
rule k8s-mass-delete - "${B}kubectl${S}${A}delete${S}+([^;&|]*${S})?(namespaces?|ns|--all|-A|--all-namespaces)${E}" \
  "Deletes a namespace or every resource of a kind. Delete named resources, after kubectl get to confirm."
rule terraform-destroy - "${B}(terraform|tofu)${S}${A}(destroy|apply${S}${A}-auto-approve)${E}" \
  "Destroys or changes infrastructure without review. Run terraform plan and show the user."
rule cloud-delete - "${B}aws${S}+s3${S}+(rm${S}[^;&|]*--recursive|rb${S}[^;&|]*--force)|${B}gcloud${S}${A}projects${S}+delete|${B}az${S}+group${S}+delete" \
  "Deletes cloud storage, a project or a resource group."
rule docker-wipe - "${B}docker${S}+(system${S}+prune${S}[^;&|]*(-[[:alnum:]]*a[[:alnum:]]*|--all|--volumes)${E}|volume${S}+(prune|rm))" \
  "Deletes Docker volumes or every image. Remove named containers or images instead."

# --- Remote code, system, publishing ---
rule pipe-to-shell - "(curl|wget)${S}[^;&]*\|${S}*(sudo${S}+)?(ba|z|da|k|fi)?sh${E}|${B}(ba|z)?sh${S}+(<\(|-c${S}+\\\$\()${S}*(curl|wget)" \
  "Runs a downloaded script unseen. Download it, show it to the user, then run it."
rule system-power - "${B}(shutdown|reboot|halt|poweroff)${E}|${B}kill${S}+(-9|-KILL|-SIGKILL)${S}+-1${E}" \
  "Shuts down the machine or kills every process."
# Publishing is checked per command, so --dry-run is allowed but
# "npm publish --dry-run && npm publish" is still caught.
while IFS= read -r part; do
  [[ $part =~ ${S}--dry-run${E} ]] && continue
  cmd=$part rule publish-package - "${B}(npm|pnpm|yarn|cargo|gem|twine|dart|flutter)${S}${A}(publish|upload|push)${E}" \
    "Publishing a package is public and permanent. Check it with --dry-run, then let the user publish."
done <<<"${cmd//[;&|]/$'\n'}"

exit 0
