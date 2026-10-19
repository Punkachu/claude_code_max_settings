#!/usr/bin/env bash
# PreToolUse hook: block Bash commands and file tools that touch .env files.
# Exit 2 blocks the call and shows stderr to Claude.
# Allowed: .env.example, .env.sample, .env.template (committed templates, no secrets).

# Fail closed: without jq we can't inspect the call.
command -v jq >/dev/null || { echo "Blocked: jq is required by the .env guardrail." >&2; exit 2; }

# Bash: check the command. File tools (Read, Edit, Write, MultiEdit, NotebookEdit, Grep): check every path field.
text=$(jq -r 'if .tool_name == "Bash" then .tool_input.command
              else .tool_input | [.file_path, .notebook_path, .path, .glob] | map(strings) | join("\n") end // empty')
for safe in .env.example .env.sample .env.template; do
  text=${text//"$safe"/}
done

# ".env" as a filename: not preceded by a name char (so process.env, foo.env pass),
# not followed by one (so .environment, .envrc pass); ".env.local" etc. still match.
if printf '%s' "$text" | grep -qE '(^|[^[:alnum:]_])\.env([^[:alnum:]_-]|$)'; then
  echo "Blocked: access to .env files is prohibited." >&2
  exit 2
fi
exit 0
