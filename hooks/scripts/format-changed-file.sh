#!/usr/bin/env bash
# PostToolUse hook: format the file Claude just edited.
# Claude Code passes details of the edit as JSON on stdin.
file=$(jq -r '.tool_input.file_path // empty')
[ -f "$file" ] || exit 0

case "$file" in
  *.ts|*.tsx|*.js|*.jsx)
    # --no-install: never download prettier into a project that doesn't use it
    npx --no-install prettier --write "$file"
    ;;
  *.go)
    gofmt -w "$file"
    ;;
  *.dart)
    dart format "$file"
    ;;
  *.py|*.pyi)
    ruff format "$file"
    ;;
  *.c|*.h|*.cc|*.cpp|*.cxx|*.hpp|*.hh|*.hxx)
    # fallback-style=none: no .clang-format in the project means leave the file alone
    clang-format -i --fallback-style=none "$file"
    ;;
  *.kt|*.kts)
    ktlint -F "$file"
    ;;
  *.swift)
    swiftformat --quiet "$file"
    ;;
esac

# A missing or failing formatter must never fail the edit.
exit 0
