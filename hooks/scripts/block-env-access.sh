#!/usr/bin/env bash
# PreToolUse hook (Bash): block shell commands that touch .env files.
# Exit 2 blocks the command and shows stderr to Claude.
# Allowed: .env.example, .env.sample, .env.template (committed templates, no secrets).

# Fail closed: without jq we can't inspect the command.
command -v jq >/dev/null || { echo "Blocked: jq is required by the .env guardrail." >&2; exit 2; }

cmd=$(jq -r '.tool_input.command // empty')
for safe in .env.example .env.sample .env.template; do
  cmd=${cmd//"$safe"/}
done

# ".env" as a filename: not preceded by a name char (so process.env, foo.env pass),
# not followed by one (so .environment, .envrc pass); ".env.local" etc. still match.
if printf '%s' "$cmd" | grep -qE '(^|[^[:alnum:]_])\.env([^[:alnum:]_-]|$)'; then
  echo "Blocked: terminal access referencing .env files is prohibited." >&2
  exit 2
fi
exit 0
