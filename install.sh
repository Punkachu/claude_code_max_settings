#!/usr/bin/env bash
# Set up the max_settings plugin's dependencies. Safe to re-run.
#   1. Installs the tools the hooks call (skips what's already installed). Needs Homebrew.
#   2. Merges the .env deny rules from .claude/settings.json into ~/.claude/settings.json.
set -euo pipefail
root=$(cd "$(dirname "$0")" && pwd)

command -v brew >/dev/null || { echo "Homebrew not found: install it from https://brew.sh" >&2; exit 1; }

# command -> brew formula
tools=(
  "jq jq"
  "npx node"
  "gofmt go"
  "ruff ruff"
  "clang-format clang-format"
  "ktlint ktlint"
  "swiftformat swiftformat"
)

for t in "${tools[@]}"; do
  read -r cmd formula <<<"$t"
  if command -v "$cmd" >/dev/null; then echo "ok       $cmd"; else echo "install  $formula"; brew install "$formula"; fi
done

# npm global (not brew): the hook calls npx --no-install, which finds npm globals.
if command -v prettier >/dev/null; then echo "ok       prettier"; else echo "install  prettier"; npm install -g prettier; fi

# Dart ships with Flutter; only install standalone Dart if neither is present.
if command -v dart >/dev/null; then
  echo "ok       dart"
else
  echo "install  dart"
  brew tap dart-lang/dart && brew install dart
fi

# Deny rules: append the ones missing, keep the user's order and other settings.
settings="$HOME/.claude/settings.json"
mkdir -p "$HOME/.claude"
[ -s "$settings" ] || echo '{}' > "$settings"
cp "$settings" "$settings.bak"
jq --argjson rules "$(jq '.permissions.deny' "$root/.claude/settings.json")" \
  '.permissions.deny = ((.permissions.deny // []) as $d | $d + ($rules - $d))' \
  "$settings" > "$settings.tmp"
mv "$settings.tmp" "$settings"
echo "ok       .env deny rules in $settings (backup: $settings.bak)"
