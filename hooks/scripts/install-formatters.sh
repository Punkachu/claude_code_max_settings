#!/usr/bin/env bash
# Install every formatter format-changed-file.sh uses. Safe to re-run: skips what's already installed.
# Needs Homebrew (macOS, or Linux via https://brew.sh).
set -euo pipefail

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
