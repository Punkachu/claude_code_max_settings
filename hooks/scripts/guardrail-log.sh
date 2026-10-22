# Sourced by the guardrail hooks. Callers set GUARD_SESSION, GUARD_CWD and GUARD_RAW
# (the raw command or path) before calling guardrail_block.
#
# Log: one tab-separated line per block in $CLAUDE_GUARDRAIL_LOG (default ~/.claude/guardrail.log):
#   time  session  rule  cwd  command (secrets masked, first 300 chars)
# Escalation: from the Nth block in one session (CLAUDE_GUARDRAIL_ESCALATE_AFTER, default 3),
# Claude is told to stop and check with the user instead of trying another workaround.

guardrail_block() { # rule, message: print the block (+ escalation), log it, exit 2
  local rule=$1 msg=$2 n=0 line
  local log=${CLAUDE_GUARDRAIL_LOG:-$HOME/.claude/guardrail.log}
  local after=${CLAUDE_GUARDRAIL_ESCALATE_AFTER:-3}

  # Best-effort masking: user:pass@ in URLs, Bearer tokens, *KEY/TOKEN/SECRET/PASS*=value.
  line=$(printf '%s' "$GUARD_RAW" | tr '\n\t' '  ' | sed -E \
    -e 's#(://[^/:@[:space:]]+:)[^@[:space:]]+@#\1***@#g' \
    -e 's#([Bb]earer[[:space:]]+)[^[:space:]"'"'"']+#\1***#g' \
    -e 's#([[:alnum:]_-]*([Kk][Ee][Yy]|[Tt][Oo][Kk][Ee][Nn]|[Ss][Ee][Cc][Rr][Ee][Tt]|[Pp][Aa][Ss][Ss])[[:alnum:]_-]*[=:][[:space:]]*)[^[:space:]&;"'"'"']+#\1***#g' |
    cut -c1-300)

  # Logging must never stop the block from happening.
  {
    mkdir -p "${log%/*}" &&
      printf '%s\t%s\t%s\t%s\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${GUARD_SESSION:--}" "$rule" "$GUARD_CWD" "$line" >>"$log"
  } 2>/dev/null
  # ponytail: counts by scanning the whole log; add rotation if it ever grows past a few MB.
  [ -n "$GUARD_SESSION" ] && n=$(awk -F'\t' -v s="$GUARD_SESSION" '$2 == s { n++ } END { print n + 0 }' "$log" 2>/dev/null)

  echo "$msg" >&2
  if [ "${n:-0}" -ge "$after" ] 2>/dev/null; then
    echo "Guardrail: this is blocked command #$n in this session. Stop trying workarounds. Tell the user what you were trying to do and why it keeps getting blocked, then wait for their go-ahead." >&2
  fi
  exit 2
}
