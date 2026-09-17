#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODE="${1:-}"

install_claude() {
  mkdir -p "$HOME/.claude/commands" "$HOME/.claude/scripts"
  cp "$ROOT/claude/deployable.md" "$HOME/.claude/commands/deployable.md"
  cp "$ROOT/bin/deployable_lms.py" "$HOME/.claude/scripts/deployable_lms.py"
  chmod 700 "$HOME/.claude/scripts/deployable_lms.py"
  echo "Installed /deployable for Claude Code."
}

install_codex() {
  TARGET="${CODEX_HOME:-$HOME/.codex}/skills/deployable"
  mkdir -p "$TARGET/scripts"
  cp "$ROOT/codex/skills/deployable/SKILL.md" "$TARGET/SKILL.md"
  cp "$ROOT/bin/deployable_lms.py" "$TARGET/scripts/deployable_lms.py"
  chmod 700 "$TARGET/scripts/deployable_lms.py"
  echo "Installed the deployable skill for Codex."
}

case "$MODE" in
  --claude) install_claude ;;
  --codex) install_codex ;;
  *) echo "Usage: ./install.sh --claude | --codex"; exit 2 ;;
esac
